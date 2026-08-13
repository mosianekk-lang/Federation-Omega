from __future__ import annotations

import os
import tempfile
import unittest

from .dag import DAGExecutor, Lane
from .routing import MemoryGovernor, MissionCompiler
from .runtime import ConnectorGateway
from .state import DurableState, EvidencePointer


class Omega3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "omega3.sqlite3")
        self.state = DurableState(self.db)
        self.compiler = MissionCompiler(self.state)
        self.plan = self.compiler.compile(
            "Lex review today's emails from Joel and Pule about the disciplinary matter.",
            mission_id="LEGAL-TEAM-INTEGRATION",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_minimum_legal_squad_and_connectors(self) -> None:
        self.assertEqual(self.plan.mission_type, "legal_email_review")
        self.assertEqual(self.plan.active_specialists, ["Lex", "LabourProcedure", "Ledger"])
        self.assertEqual(self.plan.active_connectors, ["Gmail", "Google Drive"])
        self.assertIn("Canva", self.plan.excluded_connectors)

    def test_evidence_cache_stale_detection(self) -> None:
        self.state.put_evidence(
            EvidencePointer(
                source_id="gmail:joel:1",
                source_type="gmail",
                version="v1",
                verified=True,
            )
        )
        self.assertFalse(self.state.needs_refresh("gmail:joel:1", version="v1"))
        self.assertTrue(self.state.needs_refresh("gmail:joel:1", version="v2"))

    def test_gateway_retries_and_reuses_idempotent_receipt(self) -> None:
        gateway = ConnectorGateway(self.state)
        calls = {"count": 0}

        def flaky():
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("transient")
            return {"status": "ok", "message_id": "m1"}

        first = gateway.execute(
            plan=self.plan,
            connector="Gmail",
            action="read",
            target="m1",
            fn=flaky,
            semantic_check=lambda value: value.get("status") == "ok",
        )
        self.assertEqual(first["attempts"], 2)

        second = gateway.execute(
            plan=self.plan,
            connector="Gmail",
            action="read",
            target="m1",
            fn=lambda: self.fail("idempotent result should have been reused"),
        )
        self.assertTrue(second["reused"])

    def test_irrelevant_connector_is_blocked(self) -> None:
        gateway = ConnectorGateway(self.state)
        with self.assertRaises(PermissionError):
            gateway.execute(
                plan=self.plan,
                connector="Canva",
                action="search",
                target="irrelevant",
                fn=lambda: {},
            )

    def test_failed_lane_does_not_freeze_independent_lane(self) -> None:
        executor = DAGExecutor(self.state)
        lanes = [
            Lane("joel", "read Joel"),
            Lane("pule", "read Pule"),
            Lane("policy", "read policy"),
            Lane("chronology", "build chronology", dependencies=["joel", "pule"]),
            Lane("synthesis", "legal synthesis", dependencies=["joel", "pule", "policy"]),
        ]
        handlers = {
            "joel": lambda lane: {"ok": "joel"},
            "pule": lambda lane: {"ok": "pule"},
            "policy": lambda lane: (_ for _ in ()).throw(RuntimeError("policy unavailable")),
            "chronology": lambda lane: {"chronology": "complete"},
            "synthesis": lambda lane: {"should": "not run"},
        }
        result = executor.run(self.plan.mission_id, lanes, handlers)
        self.assertEqual(result["lanes"]["chronology"]["state"], "COMPLETE")
        self.assertEqual(result["lanes"]["policy"]["state"], "FAILED")
        self.assertEqual(result["lanes"]["synthesis"]["state"], "BLOCKED")
        self.assertIsNotNone(self.state.latest_checkpoint(self.plan.mission_id))

    def test_hot0_hot1_warm_cold_memory(self) -> None:
        memory = MemoryGovernor().classify(
            {
                "objective": self.plan.objective,
                "current_question": "What do the messages mean?",
                "needed_facts": ["fact1", "fact2"],
                "needed_source_pointers": ["gmail:joel:1", "gmail:pule:1"],
                "verified_facts": ["verified1"],
                "active_source_pointers": ["gmail:joel:1"],
                "project_state_pointer": "drive:project-state",
                "archive_pointer": "drive:archive",
            }
        )
        self.assertIn("HOT_0", memory)
        self.assertIn("HOT_1", memory)
        self.assertIn("WARM", memory)
        self.assertIn("COLD", memory)
        self.assertEqual(len(memory["capsule_sha256"]), 64)

    def test_adaptive_budget_tightens_under_latency(self) -> None:
        baseline = self.compiler.budgeter.retrieval_budget()
        self.state.update_metric("connector.latency_ms", 2500)
        tightened = self.compiler.budgeter.retrieval_budget()
        self.assertLessEqual(tightened, baseline)


if __name__ == "__main__":
    unittest.main()
