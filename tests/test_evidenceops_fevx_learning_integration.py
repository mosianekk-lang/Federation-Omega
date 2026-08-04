from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evidenceops.fevx_adapter_v1.learning_integration import (
    capture_evidenceops_fevx_run,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_learning_policy.json"


class EvidenceOpsFEVXLearningIntegrationTests(unittest.TestCase):
    def test_verified_run_records_success_and_held_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = capture_evidenceops_fevx_run(
                result={
                    "status": "VERIFIED",
                    "checks": {"case_wall": True, "readback": True},
                    "real_case_accuracy_evidence": False,
                    "level_6_eligible": False,
                    "external_effect": False,
                },
                workspace=directory,
                policy_path=POLICY,
                source_run_id="RUN-1",
                evidence_refs=["provider-proof:RUN-1"],
            )
            self.assertEqual("PASSED", result["verification"]["status"])
            event_types = {row["event_type"] for row in result["events"]}
            self.assertIn("SUCCESS", event_types)
            self.assertIn("CONSTRAINT", event_types)
            self.assertFalse(result["external_effect"])
            self.assertFalse(result["source_write"])
            self.assertFalse(result["verified_fact_write"])

    def test_exception_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = capture_evidenceops_fevx_run(
                result=None,
                workspace=directory,
                policy_path=POLICY,
                source_run_id="RUN-2",
                exception=RuntimeError("schema mismatch"),
            )
            self.assertEqual("PASSED", result["verification"]["status"])
            self.assertEqual("FAILURE", result["events"][0]["event_type"])
            actions = {
                activation["action"]
                for event in result["events"]
                for activation in event.get("trigger_activations", [])
            }
            self.assertIn("FORWARD_FIX", actions)


if __name__ == "__main__":
    unittest.main()
