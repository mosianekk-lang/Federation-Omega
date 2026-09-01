from __future__ import annotations

import unittest

from mission_autonomy import MissionAutonomyEngine, MissionGoal, WorkUnit


class MissionAutonomyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = MissionAutonomyEngine(MissionGoal("m1", "complete mission", ("provider-proof",)))
        self.engine.decompose([
            WorkUnit("discover", "discover", required_receipts=("provider-proof",), priority=90),
            WorkUnit("analyse", "analyse", dependencies=("discover",), priority=80),
            WorkUnit("blocked", "blocked route", blocked=True),
        ])

    def test_decomposition_ready_and_optimisation(self) -> None:
        self.assertEqual(self.engine.ready()[0]["work_id"], "discover")
        self.assertEqual(self.engine.optimise(2), ["discover"])

    def test_cycle_detection_fails_closed(self) -> None:
        engine = MissionAutonomyEngine(MissionGoal("m-cycle", "reject cycle", ()))
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            engine.decompose([
                WorkUnit("a", "a", dependencies=("b",)),
                WorkUnit("b", "b", dependencies=("a",)),
            ])

    def test_completion_contract_and_closure(self) -> None:
        partial = self.engine.mark_verified("discover", {})
        self.assertEqual(partial["status"], "PARTIALLY_VERIFIED")
        self.engine.plan.units["discover"]["status"] = "QUEUED"
        self.engine.mark_verified("discover", {"provider-proof": {"ok": True}})
        self.engine.mark_verified("analyse", {})
        self.engine.substitute_blocked("blocked", WorkUnit("alternate", "alternate", substitute_for="blocked"))
        self.engine.mark_verified("alternate", {"provider-proof": {"ok": True}})
        self.assertEqual(self.engine.evaluate_closure()["state"], "PROOF_CLOSED")

    def test_blocked_substitution_and_dynamic_replan(self) -> None:
        revision = self.engine.plan.revision
        row = self.engine.substitute_blocked("blocked", WorkUnit("alternate", "alternate", substitute_for="blocked"))
        self.assertEqual(row["status"], "QUEUED")
        self.assertGreater(self.engine.plan.revision, revision)
        repair = self.engine.replan_failed("discover", WorkUnit("discover-repair", "repair discovery"))
        self.assertEqual(repair["status"], "QUEUED")
        self.assertIn("provider-proof", repair["required_receipts"])
        self.assertEqual(self.engine.plan.units["discover"]["status"], "SUPERSEDED")
        self.assertEqual(self.engine.plan.units["discover"]["superseded_by"], "discover-repair")

    def test_failed_path_successor_unblocks_dependants_and_allows_closure(self) -> None:
        engine = MissionAutonomyEngine(MissionGoal("m2", "repair and continue", ("provider-proof",)))
        engine.decompose([
            WorkUnit("discover", "discover", required_receipts=("provider-proof",)),
            WorkUnit("analyse", "analyse", dependencies=("discover",)),
        ])
        engine.replan_failed("discover", WorkUnit("discover-repair", "repair discovery"))
        self.assertEqual([row["work_id"] for row in engine.ready()], ["discover-repair"])
        engine.mark_verified("discover-repair", {"provider-proof": {"ok": True}})
        self.assertEqual([row["work_id"] for row in engine.ready()], ["analyse"])
        engine.mark_verified("analyse", {})
        self.assertEqual(engine.evaluate_closure()["state"], "PROOF_CLOSED")

    def test_mission_constraints_are_enforced(self) -> None:
        engine = MissionAutonomyEngine(MissionGoal("m3", "constraint", (), constraints=("budget_ok",)))
        engine.decompose([WorkUnit("a", "a")])
        engine.mark_verified("a", {})
        self.assertEqual(engine.evaluate_closure()["state"], "OPEN")
        self.assertEqual(engine.evaluate_closure({"budget_ok"})["state"], "PROOF_CLOSED")

    def test_closure_refuses_missing_proof(self) -> None:
        result = self.engine.evaluate_closure()
        self.assertEqual(result["state"], "OPEN")
        self.assertTrue(result["incomplete_work"])
        self.assertIn("provider-proof", result["missing_receipts"])


if __name__ == "__main__":
    unittest.main()
