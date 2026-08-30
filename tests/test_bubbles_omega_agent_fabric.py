from __future__ import annotations

import unittest

from bubbles.agent_fabric import (
    BubblesOmegaAgentFabric,
    DirectiveMission,
    DirectiveTask,
    EffectClass,
    EffectPermit,
    MissionState,
    TaskState,
)


class BubblesOmegaAgentFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = BubblesOmegaAgentFabric()

    @staticmethod
    def mission() -> DirectiveMission:
        return DirectiveMission(
            mission_id="M-001",
            objective="Complete a directive with proof",
            tasks=(
                DirectiveTask("discover", "Find sources", ("research",)),
                DirectiveTask("build", "Build implementation", ("software", "testing"), depends_on=("discover",)),
                DirectiveTask("prove", "Verify proof", ("proof", "readback"), depends_on=("build",)),
            ),
        )

    def test_compile_builds_dependency_waves_and_agents_plus_bots(self) -> None:
        plan = self.fabric.compile(self.mission())
        self.assertEqual((("discover",), ("build",), ("prove",)), plan.waves)
        self.assertFalse(plan.unresolved_tasks)
        assignment = next(item for item in plan.assignments if item.task_id == "build")
        self.assertIn("BUBBLES-OMEGA-FORGE", assignment.primary_agents)
        self.assertIn("BUBBLES-OMEGA-PROOF-BOT", assignment.support_bots)
        self.assertIn("BUBBLES-OMEGA-CHECKPOINT-BOT", assignment.support_bots)

    def test_cycle_fails_closed(self) -> None:
        mission = DirectiveMission(
            "cycle",
            "bad graph",
            (
                DirectiveTask("a", "a", ("research",), depends_on=("b",)),
                DirectiveTask("b", "b", ("software",), depends_on=("a",)),
            ),
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.fabric.compile(mission)

    def test_unrelated_lane_remains_ready(self) -> None:
        mission = DirectiveMission(
            "parallel",
            "isolate failures",
            (
                DirectiveTask("a", "lane a", ("research",)),
                DirectiveTask("b", "lane b", ("software",)),
                DirectiveTask("c", "depends a", ("proof",), depends_on=("a",)),
            ),
        )
        self.fabric.task_state[("parallel", "a")] = TaskState.FAILURE
        self.assertIn("b", self.fabric.ready_tasks(mission))
        self.assertNotIn("c", self.fabric.ready_tasks(mission))

    def test_read_only_provider_task_requires_exact_permit(self) -> None:
        mission = DirectiveMission(
            "provider",
            "read provider",
            (DirectiveTask("read", "read", ("provider-read",), target="drive", effect=EffectClass.READ_ONLY_PROVIDER),),
        )
        blocked = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="route-a",
        )
        self.assertEqual(TaskState.CONSTRAINT, blocked.state)
        self.fabric.reopen_task(mission, "read", changed_route_fingerprint="route-b")
        permit = EffectPermit("p1", "provider", "read", "drive", EffectClass.READ_ONLY_PROVIDER)
        passed = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["provider-readback-1"]},
            route_fingerprint="route-b",
            permit=permit,
        )
        self.assertEqual(TaskState.SUCCESS, passed.state)
        self.assertIn("provider-readback-1", passed.evidence_refs)

    def test_default_fleet_does_not_inherit_write_authority(self) -> None:
        mission = DirectiveMission(
            "write",
            "write provider",
            (DirectiveTask("write", "write", ("integration",), target="provider", effect=EffectClass.REVERSIBLE_WRITE),),
        )
        plan = self.fabric.compile(mission)
        self.assertEqual(("write",), plan.unresolved_tasks)

    def test_idempotency_returns_same_success_receipt(self) -> None:
        mission = DirectiveMission("idem", "once", (DirectiveTask("x", "x", ("research",), idempotency_key="same"),))
        calls = {"count": 0}

        def executor(*_):
            calls["count"] += 1
            return {"state": "SUCCESS"}

        one = self.fabric.run_task(mission=mission, task_id="x", executor=executor, route_fingerprint="r1")
        two = self.fabric.run_task(mission=mission, task_id="x", executor=executor, route_fingerprint="r2")
        self.assertEqual(one.receipt_id, two.receipt_id)
        self.assertEqual(1, calls["count"])

    def test_unchanged_failed_route_is_quarantined(self) -> None:
        mission = DirectiveMission("retry", "recover", (DirectiveTask("x", "x", ("research",)),))
        failed = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "FAILURE"},
            route_fingerprint="bad-route",
        )
        self.assertEqual(TaskState.FAILURE, failed.state)
        self.fabric.reopen_task(mission, "x", changed_route_fingerprint="new-route")
        held = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="bad-route",
        )
        self.assertEqual(TaskState.CONSTRAINT, held.state)
        self.assertIn("UNCHANGED_FAILED_ROUTE", held.note)

    def test_guard_and_verifier_fail_closed(self) -> None:
        mission = DirectiveMission("verify", "verify", (DirectiveTask("x", "x", ("research",)),))
        held = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="r1",
            guard=lambda _: (False, "REALITYGUARD_HOLD"),
        )
        self.assertEqual(TaskState.CONSTRAINT, held.state)
        self.fabric.reopen_task(mission, "x", changed_route_fingerprint="r2")
        held2 = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="r2",
            verifier=lambda *_: (False, "NO_SEMANTIC_READBACK", ("j1",)),
        )
        self.assertEqual(TaskState.CONSTRAINT, held2.state)
        self.assertIn("j1", held2.evidence_refs)

    def test_completion_requires_every_required_task_success(self) -> None:
        mission = self.mission()
        for task_id in ("discover", "build", "prove"):
            self.fabric.run_task(
                mission=mission,
                task_id=task_id,
                executor=lambda *_: {"state": "SUCCESS", "evidence_refs": [f"proof-{task_id}"]},
                route_fingerprint=f"route-{task_id}",
            )
        self.assertEqual(MissionState.COMPLETE, self.fabric.mission_state(mission))
        receipt = self.fabric.completion_receipt(mission)
        self.assertTrue(receipt["directive_complete"])
        self.assertEqual(3, len(receipt["proof_refs"]))

    def test_benchmark_snapshot_records_observed_agent_work(self) -> None:
        mission = DirectiveMission("metrics", "measure", (DirectiveTask("x", "x", ("research",)),))
        self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="r1",
        )
        snapshot = self.fabric.benchmark_snapshot()
        self.assertEqual(1, snapshot["BUBBLES-OMEGA-SCOUT"]["attempts"])
        self.assertEqual(1.0, snapshot["BUBBLES-OMEGA-SCOUT"]["reliability"])


if __name__ == "__main__":
    unittest.main()
