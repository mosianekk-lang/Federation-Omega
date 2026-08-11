from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from federation_learning import EventType, LearningFabric, LearningFabricError


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_learning_policy.json"


class LearningFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.fabric = LearningFabric(self.workspace, policy_path=POLICY)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def record(self, event_type: EventType, summary: str, **kwargs):
        return self.fabric.record(
            event_type=event_type,
            system_id="SYSTEM",
            workflow_id="WORKFLOW",
            mission_id="MISSION",
            summary=summary,
            source_run_id=kwargs.pop("source_run_id", "RUN-1"),
            **kwargs,
        )

    def test_success_is_append_only_and_chain_verifies(self) -> None:
        event = self.record(EventType.SUCCESS, "Canary passed")
        self.assertEqual("SUCCESS", event["event_type"])
        self.assertEqual("PASSED", self.fabric.verify_chain()["status"])
        self.assertEqual(1, self.fabric.verify_chain()["event_count"])

    def test_exact_capture_is_idempotent(self) -> None:
        first = self.record(EventType.SUCCESS, "Canary passed")
        second = self.record(EventType.SUCCESS, "Canary passed")
        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(1, self.fabric.verify_chain()["event_count"])

    def test_failure_classification_activates_repair(self) -> None:
        self.record(
            EventType.FAILURE,
            "Schema validation failed",
            details={"message": "missing required field"},
        )
        state = json.loads(self.fabric.trigger_state_path.read_text())
        actions = {row["action"] for row in state["activations"].values()}
        self.assertIn("FORWARD_FIX", actions)
        self.assertIn("ADD_REGRESSION_TEST", actions)
        self.assertIn("PRESERVE_FAILURE_EVIDENCE", actions)

    def test_repeated_failure_opens_circuit(self) -> None:
        self.record(
            EventType.FAILURE,
            "Provider timeout",
            source_run_id="RUN-1",
        )
        self.record(
            EventType.FAILURE,
            "Provider timeout",
            source_run_id="RUN-2",
        )
        state = json.loads(self.fabric.trigger_state_path.read_text())
        actions = {row["action"] for row in state["activations"].values()}
        self.assertIn("OPEN_CIRCUIT", actions)
        self.assertIn("ALTERNATE_ROUTE_REQUIRED", actions)

    def test_authority_constraint_halts_effectful_route(self) -> None:
        self.record(
            EventType.CONSTRAINT,
            "Operator token unavailable",
            category="AUTHORITY",
        )
        state = json.loads(self.fabric.trigger_state_path.read_text())
        actions = {row["action"] for row in state["activations"].values()}
        self.assertIn("HALT_EFFECTFUL_ROUTE", actions)
        self.assertIn("CREATE_RECOVERY_PACKAGE", actions)

    def test_success_after_failure_binds_regression(self) -> None:
        self.record(EventType.FAILURE, "Validation failed", source_run_id="RUN-1")
        self.record(EventType.SUCCESS, "Validation passed after repair", source_run_id="RUN-2")
        state = json.loads(self.fabric.trigger_state_path.read_text())
        actions = {row["action"] for row in state["activations"].values()}
        self.assertIn("BIND_REGRESSION_TEST", actions)
        self.assertIn("PRESERVE_BEFORE_AFTER_EVIDENCE", actions)

    def test_repeated_success_is_candidate_not_trust_transfer(self) -> None:
        self.record(EventType.SUCCESS, "Readback passed", source_run_id="RUN-1")
        self.record(EventType.SUCCESS, "Readback passed", source_run_id="RUN-2")
        state = json.loads(self.fabric.trigger_state_path.read_text())
        by_action = {row["action"]: row for row in state["activations"].values()}
        self.assertEqual(
            "CANDIDATE",
            by_action["ROUTE_CONFIDENCE_INCREASE_CANDIDATE"]["state"],
        )
        self.assertIn("NO_TRUST_TRANSFER", by_action)

    def test_correction_propagation_trigger(self) -> None:
        self.record(EventType.CORRECTION, "User corrected the active pathway")
        state = json.loads(self.fabric.trigger_state_path.read_text())
        actions = {row["action"] for row in state["activations"].values()}
        self.assertIn("PROPAGATE_CORRECTION", actions)
        self.assertIn("RETEST_AFFECTED_SCOPE", actions)

    def test_secret_fields_and_values_are_redacted(self) -> None:
        github_token = "gh" + "p_" + ("A" * 30)
        openai_token = "sk-" + "proj-" + ("B" * 24)
        event = self.record(
            EventType.FAILURE,
            f"Credential leaked {github_token}",
            details={
                "access_token": github_token,
                "message": openai_token,
            },
        )
        rendered = json.dumps(event)
        self.assertNotIn(github_token, rendered)
        self.assertNotIn(openai_token, rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_authority_expansion_is_rejected(self) -> None:
        with self.assertRaises(LearningFabricError):
            self.fabric.record(
                event_type=EventType.SUCCESS,
                system_id="SYSTEM",
                workflow_id="WORKFLOW",
                mission_id="MISSION",
                summary="Unsafe authority",
                authority="A2_EXTERNAL",
            )

    def test_external_effect_is_rejected(self) -> None:
        with self.assertRaises(LearningFabricError):
            self.fabric.record(
                event_type=EventType.SUCCESS,
                system_id="SYSTEM",
                workflow_id="WORKFLOW",
                mission_id="MISSION",
                summary="Unsafe effect",
                external_effect=True,
            )

    def test_tamper_is_detected(self) -> None:
        self.record(EventType.SUCCESS, "Canary passed")
        rows = self.fabric.ledger_path.read_text().splitlines()
        payload = json.loads(rows[0])
        payload["summary"] = "tampered"
        self.fabric.ledger_path.write_text(json.dumps(payload) + "\n")
        self.assertEqual("FAILED", self.fabric.verify_chain()["status"])

    def test_capture_result_records_failed_checks_and_constraints(self) -> None:
        events = self.fabric.capture_result(
            {
                "status": "FAILED_VERIFICATION",
                "checks": {"schema": False, "readback": True},
                "blockers": ["provider identity unavailable"],
            },
            system_id="SYSTEM",
            workflow_id="WORKFLOW",
            mission_id="MISSION",
            source_run_id="RUN-9",
        )
        self.assertGreaterEqual(len(events), 3)
        summary = self.fabric.summary()
        self.assertEqual("PASSED", summary["chain"]["status"])
        self.assertGreaterEqual(summary["event_type_counts"]["FAILURE"], 2)
        self.assertGreaterEqual(summary["event_type_counts"]["CONSTRAINT"], 1)


if __name__ == "__main__":
    unittest.main()
