from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ao_harmonic_v3.operational_transition import run_operational_transition_capsule
from ao_harmonic_v3.provider_workflow import run_provider_workflow_capsule


CYCLE2 = Path("governance/ao_harmonic_v3_workflow_cycle2_capsule.json")
TRANSITION = Path("governance/ao_harmonic_v3_operational_transition_capsule.json")
EXPECTED_CYCLE2_RECEIPT = "2227bb222ca21308b5c5387453549f14c513e61056f2e63c04ccd90b647b3175"


class AOHarmonicOperationalTransitionTests(unittest.TestCase):
    def test_second_independent_stable_workflow_cycle_executes(self):
        payload = json.loads(CYCLE2.read_text(encoding="utf-8"))
        receipt = run_provider_workflow_capsule(payload, provider_runtime="GITHUB_ACTIONS")
        self.assertEqual(receipt["workflow_status"], "PASS")
        self.assertEqual(receipt["receipt_sha256"], EXPECTED_CYCLE2_RECEIPT)
        self.assertFalse(receipt["truth_boundary"]["operationally_verified"])

    def test_real_provider_transition_recomputes_state_proof_and_mission(self):
        payload = json.loads(TRANSITION.read_text(encoding="utf-8"))
        receipt = run_operational_transition_capsule(payload, provider_runtime="GITHUB_ACTIONS")
        self.assertEqual(receipt["workflow_status"], "PASS")
        self.assertTrue(receipt["real_provider_state_change_observed"])
        self.assertTrue(receipt["immutable_event_history_preserved"])
        self.assertTrue(receipt["proof_impact_propagated"])
        self.assertTrue(receipt["mission_recomputed"])
        self.assertEqual(receipt["before_status"], "NOT_FOUND")
        self.assertEqual(receipt["after_status"], "FOUND")
        self.assertNotIn("dependent_internal", receipt["ready_after_baseline"])
        self.assertIn("dependent_internal", receipt["ready_after_change"])
        self.assertIn("unrelated_internal", receipt["ready_after_change"])
        self.assertEqual(receipt["prior_workflow_cycle_count"], 2)
        self.assertEqual(receipt["jarvis_defects"], [])
        self.assertEqual(
            receipt["maturity_candidate"],
            "OPERATIONAL_VERIFIED_PENDING_INDEPENDENT_POST_RUNTIME_PROVIDER_READBACK",
        )
        self.assertFalse(receipt["provider_mutation_caused_by_runtime"])
        self.assertFalse(receipt["truth_boundary"]["operationally_verified"])
        self.assertTrue(
            receipt["truth_boundary"]["independent_post_runtime_provider_readback_pending"]
        )
        print(
            "AO_HARMONIC_OPERATIONAL_TRANSITION_RUNTIME_RECEIPT="
            + json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        )

    def test_unchanged_provider_state_cannot_fake_operational_maturity(self):
        payload = json.loads(TRANSITION.read_text(encoding="utf-8"))
        payload["before"] = copy.deepcopy(payload["after"])
        payload["expected_transition"] = {"from": "FOUND", "to": "FOUND"}
        with self.assertRaises(ValueError):
            run_operational_transition_capsule(payload, provider_runtime="GITHUB_ACTIONS")

    def test_runtime_cannot_claim_it_caused_provider_mutation(self):
        payload = json.loads(TRANSITION.read_text(encoding="utf-8"))
        payload["provider_mutation_caused_by_runtime"] = True
        with self.assertRaises(ValueError):
            run_operational_transition_capsule(payload, provider_runtime="GITHUB_ACTIONS")


if __name__ == "__main__":
    unittest.main()
