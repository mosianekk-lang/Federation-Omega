from __future__ import annotations

import json
import unittest
from pathlib import Path

from ao_harmonic_v3.canonical_qualification import run_canonical_qualification

CAPSULE = Path("governance/ao_harmonic_v3_canonical_qualification_capsule.json")


class AOHarmonicCanonicalQualificationTests(unittest.TestCase):
    def payload(self):
        return json.loads(CAPSULE.read_text(encoding="utf-8"))

    def test_real_adverse_recovery_multi_provider_sequence_qualifies(self):
        receipt = run_canonical_qualification(self.payload(), provider_runtime="GITHUB_ACTIONS")
        self.assertEqual(receipt["qualification_status"], "PASS")
        self.assertEqual(receipt["immutable_event_history"], ["baseline", "adverse", "recovery"])
        self.assertTrue(receipt["stale_baseline_contradicted"])
        self.assertTrue(receipt["adverse_state_contradicted_after_recovery"])
        self.assertTrue(receipt["recovery_state_verified"])
        self.assertTrue(receipt["mission_recovered"])
        self.assertTrue(receipt["unrelated_lane_continued"])
        self.assertTrue(receipt["independent_provider_pass"])
        self.assertEqual(receipt["provider_class_count"], 3)
        self.assertFalse(receipt["external_effect"])
        self.assertFalse(receipt["provider_mutation_caused_by_runtime"])
        self.assertFalse(receipt["truth_boundary"]["global_federation_canonical"])
        print("AO_HARMONIC_CANONICAL_QUALIFICATION_RUNTIME_RECEIPT=" + json.dumps(receipt, sort_keys=True, separators=(",", ":")))

    def test_stable_sequence_cannot_fake_canonical_qualification(self):
        payload = self.payload()
        payload["adverse_recovery_sequence"][1]["observed_status"] = "FOUND"
        payload["adverse_recovery_sequence"][1]["expected_status"] = "FOUND"
        with self.assertRaises(ValueError):
            run_canonical_qualification(payload, provider_runtime="GITHUB_ACTIONS")

    def test_same_provider_cannot_fake_multi_provider_diversity(self):
        payload = self.payload()
        payload["independent_provider_cycle"]["provider"] = "GoogleDrive"
        with self.assertRaises(ValueError):
            run_canonical_qualification(payload, provider_runtime="GITHUB_ACTIONS")

    def test_external_effect_is_rejected(self):
        payload = self.payload()
        payload["external_effect"] = True
        with self.assertRaises(ValueError):
            run_canonical_qualification(payload, provider_runtime="GITHUB_ACTIONS")

    def test_runtime_cannot_claim_it_caused_provider_mutation(self):
        payload = self.payload()
        payload["provider_mutation_caused_by_runtime"] = True
        with self.assertRaises(ValueError):
            run_canonical_qualification(payload, provider_runtime="GITHUB_ACTIONS")


if __name__ == "__main__":
    unittest.main()
