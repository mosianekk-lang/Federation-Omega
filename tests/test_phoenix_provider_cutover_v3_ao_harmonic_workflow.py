from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ao_harmonic_v3.provider_workflow import run_provider_workflow_capsule


CAPSULE = Path("governance/ao_harmonic_v3_workflow_capsule.json")


class AOHarmonicProviderWorkflowTests(unittest.TestCase):
    def test_live_provider_derived_capsule_executes_ao_harmonic_runtime(self):
        payload = json.loads(CAPSULE.read_text(encoding="utf-8"))
        receipt = run_provider_workflow_capsule(payload, provider_runtime="GITHUB_ACTIONS")
        self.assertEqual(receipt["workflow_status"], "PASS")
        self.assertTrue(receipt["package_runtime_executed"])
        self.assertTrue(receipt["event_state_proof_mission_propagation"])
        self.assertEqual(receipt["semantic_readback"], "SUCCESS")
        self.assertEqual(receipt["jarvis_defects"], [])
        self.assertIn("dependent_internal", receipt["ready_node_ids"])
        self.assertIn("unrelated_internal", receipt["ready_node_ids"])
        self.assertEqual(
            receipt["maturity_candidate"],
            "WORKFLOW_VERIFIED_PENDING_INDEPENDENT_OBSERVED_PROVIDER_READBACK",
        )
        self.assertTrue(
            receipt["truth_boundary"]["github_actions_provider_runtime_execution_verified"]
        )
        self.assertTrue(
            receipt["truth_boundary"]["independent_observed_provider_readback_pending"]
        )
        self.assertFalse(receipt["truth_boundary"]["workflow_verified"])
        self.assertFalse(receipt["truth_boundary"]["operationally_verified"])
        self.assertFalse(receipt["external_effect"])

    def test_cli_entrypoint_executes_capsule_and_emits_provider_runtime_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "workflow-receipt.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ao_harmonic_v3.provider_workflow",
                    "--input",
                    str(CAPSULE),
                    "--output",
                    str(output),
                    "--provider-runtime",
                    "GITHUB_ACTIONS",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("AO_HARMONIC_PROVIDER_WORKFLOW_RECEIPT=", proc.stdout)
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(receipt["workflow_status"], "PASS")
            self.assertTrue(receipt["package_runtime_executed"])
            print(
                "AO_HARMONIC_WORKFLOW_RUNTIME_RECEIPT="
                + json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            )

    def test_workflow_rejects_external_effect_capsule(self):
        payload = json.loads(CAPSULE.read_text(encoding="utf-8"))
        payload["external_effect"] = True
        with self.assertRaises(ValueError):
            run_provider_workflow_capsule(payload, provider_runtime="GITHUB_ACTIONS")

    def test_workflow_rejects_unknown_provider_runtime(self):
        payload = json.loads(CAPSULE.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            run_provider_workflow_capsule(payload, provider_runtime="UNKNOWN_RUNTIME")


if __name__ == "__main__":
    unittest.main()
