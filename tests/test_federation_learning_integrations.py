from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from federation_learning import LearningFabric
from federation_learning.integrations import (
    capture_alpha_omega_maintenance,
    capture_resolve_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_learning_policy.json"


class FederationLearningIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.fabric = LearningFabric(self.temp.name, policy_path=POLICY)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_alpha_omega_report_captures_drift_failure_and_terminal_state(self) -> None:
        events = capture_alpha_omega_maintenance(
            self.fabric,
            {
                "system_id": "AO-SYSTEM",
                "state": "MAINTENANCE_ACTION_REQUIRED",
                "drift": {"drift": True, "changed": ["version"]},
                "failure": {"category": "CONTRACT", "retryable": False},
                "repair": {"action": "FORWARD_FIX_AND_RETEST"},
                "retirement": {"retire": False, "triggers": []},
                "report_sha256": "abc",
            },
            mission_id="MISSION",
            source_run_id="AO-RUN-1",
        )
        types = [event["event_type"] for event in events]
        self.assertIn("FAILURE", types)
        self.assertGreaterEqual(types.count("CONSTRAINT"), 2)
        actions = {
            activation["action"]
            for event in events
            for activation in event.get("trigger_activations", [])
        }
        self.assertIn("ROLLBACK_TO_VERIFIED_CHECKPOINT", actions)
        self.assertIn("ADD_REGRESSION_TEST", actions)

    def test_resolve_receipt_captures_lane_failure_and_verified_completion(self) -> None:
        events = capture_resolve_receipt(
            self.fabric,
            {
                "job_id": "JOB-1",
                "status": "COMPLETE_VERIFIED",
                "proof_level": "COMPLETE_VERIFIED",
                "reason": "",
                "attempts": [
                    {
                        "attempt": 1,
                        "lane_id": "LANE-A",
                        "status": "FAILED",
                        "failure_class": "TRANSIENT",
                        "details": {"message": "timeout"},
                    },
                    {
                        "attempt": 2,
                        "lane_id": "LANE-B",
                        "status": "SUCCESS",
                        "failure_class": None,
                        "details": {"receipt": "verified"},
                    },
                ],
                "gates": [{"gate_id": "readback", "passed": True}],
            },
            mission_id="MISSION",
            source_run_id="RESOLVE-RUN-1",
        )
        types = [event["event_type"] for event in events]
        self.assertIn("FAILURE", types)
        self.assertEqual(2, types.count("SUCCESS"))
        actions = {
            activation["action"]
            for event in events
            for activation in event.get("trigger_activations", [])
        }
        self.assertIn("BOUNDED_RETRY_WITH_BACKOFF", actions)
        self.assertIn("BIND_REGRESSION_TEST", actions)
        self.assertEqual("PASSED", self.fabric.verify_chain()["status"])


if __name__ == "__main__":
    unittest.main()
