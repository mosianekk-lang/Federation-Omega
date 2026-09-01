from __future__ import annotations

import json
from pathlib import Path
import unittest

from benchmarking.cfbe_omega.prospective_observation_cohort_v1 import (
    validate_cohort_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
COHORT_DIR = ROOT / "benchmarking" / "cfbe_omega" / "cohorts"
SOURCE = "b5db020c89819fb5ac193612be5f6249d21a514e"
CHAMPION = "BUBBLES-CFBE-INCUMBENT-B5DB020"
CANDIDATE = "BCO-PRIME-V1-B5DB020"
PATHS = tuple(
    COHORT_DIR / f"BCO_PRIME_VALUE_COHORT_{index:03d}.json"
    for index in range(1, 4)
)
EXPECTED_RECEIPTS = (
    "sha256:401f987eea9433bbd1cf4097f57cd84da57a57ec1f2bfcacc5903a0289a0c283",
    "sha256:183a5f5c5e362a947ee297e2b7fd4f67c51ab02e600981cf3f75a2d08c0b97d2",
    "sha256:990630caf4b21d11f96e8c261b76edfbd00d14d3b8cd6c65f0ff7dbbf3520ef0",
)


class BCOPrimeProspectiveValueCohortsV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payloads = tuple(
            json.loads(path.read_text(encoding="utf-8")) for path in PATHS
        )

    def test_each_manifest_passes_existing_cohort_validator(self):
        for payload in self.payloads:
            validate_cohort_manifest(payload)

    def test_three_cohorts_create_exactly_thirty_unique_real_slots(self):
        slots = [slot for payload in self.payloads for slot in payload["slots"]]
        self.assertEqual(30, len(slots))
        self.assertEqual(30, len({slot["slot_id"] for slot in slots}))
        self.assertEqual(30, len({slot["pair_id"] for slot in slots}))
        self.assertEqual(30, len({slot["task_oracle_id"] for slot in slots}))
        self.assertEqual(30, len({slot["task_class"] for slot in slots}))
        self.assertEqual(
            {f"BCO-PRIME-REAL-TASK-ORACLE-{index:02d}" for index in range(1, 31)},
            {slot["task_oracle_id"] for slot in slots},
        )

    def test_cohorts_are_frozen_to_the_qualified_prime_source_and_policy_pair(self):
        for payload in self.payloads:
            self.assertEqual(SOURCE, payload["source_head_sha"])
            self.assertEqual(CHAMPION, payload["champion_id"])
            self.assertEqual(CANDIDATE, payload["candidate_id"])
            self.assertEqual(10, payload["minimum_owner_value_pairs"])
            self.assertEqual("REGISTERED_AWAITING_PROSPECTIVE_OBSERVATIONS", payload["state"])

    def test_registration_contains_zero_observed_or_compiled_results(self):
        for payload in self.payloads:
            self.assertEqual(0, payload["observed_baseline_count"])
            self.assertEqual(0, payload["observed_candidate_count"])
            self.assertEqual(0, payload["compiled_pair_count"])
            self.assertFalse(payload["owner_value_proven"])
            self.assertFalse(payload["provider_deployment_proven"])
            self.assertFalse(payload["stable_promotion_allowed"])
            self.assertFalse(payload["provider_effect_authorized"])
            self.assertFalse(payload["external_effect"])
            for slot in payload["slots"]:
                self.assertEqual("AWAITING_PROSPECTIVE_PAIR", slot["status"])
                self.assertTrue(slot["real_observation_required"])
                self.assertFalse(slot["synthetic_observation_allowed"])
                self.assertFalse(slot["shadow_observation_allowed"])
                self.assertFalse(slot["baseline_received"])
                self.assertFalse(slot["candidate_received"])
                self.assertFalse(slot["pair_compiled"])

    def test_receipts_are_exact_and_distinct(self):
        receipts = tuple(payload["receipt_sha256"] for payload in self.payloads)
        self.assertEqual(EXPECTED_RECEIPTS, receipts)
        self.assertEqual(3, len(set(receipts)))

    def test_registration_cannot_be_interpreted_as_prime_promotion(self):
        total_pairs = sum(payload["compiled_pair_count"] for payload in self.payloads)
        any_owner_value = any(payload["owner_value_proven"] for payload in self.payloads)
        any_effect = any(payload["provider_effect_authorized"] for payload in self.payloads)
        any_stable = any(payload["stable_promotion_allowed"] for payload in self.payloads)
        self.assertEqual(0, total_pairs)
        self.assertFalse(any_owner_value)
        self.assertFalse(any_effect)
        self.assertFalse(any_stable)


if __name__ == "__main__":
    unittest.main()
