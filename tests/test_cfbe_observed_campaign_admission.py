from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from federation.cfbe_observed_campaign_admission import (
    DEFAULT_RECEIPT_PATH,
    _validate_decoded_receipt,
    admit_observed_campaign,
)


SOURCE = DEFAULT_RECEIPT_PATH


def encoded(value: dict) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True).encode("utf-8")


class ObservedCampaignAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = SOURCE.read_bytes()
        self.receipt = json.loads(self.raw)

    def test_exact_receipt_is_admitted_without_promotion(self) -> None:
        result = admit_observed_campaign(self.raw)
        self.assertEqual(
            "ADMISSIBLE_AS_SEPARATE_OBSERVED_EMPIRICAL_VALUE_CANDIDATE",
            result["decision"],
        )
        self.assertEqual("ADAPTER_VALIDATED_NOT_PROVIDER_REGISTERED", result["canonical_admission_state"])
        self.assertEqual(30, result["observed_pair_count"])
        self.assertFalse(result["stable_promotion_allowed"])
        self.assertFalse(result["provider_authority_granted"])

    def test_default_receipt_path_is_repository_native(self) -> None:
        self.assertTrue(SOURCE.is_file())
        self.assertEqual(
            "benchmarking/cfbe_omega/bubbles_30_pair_observed_certification_20260830.json",
            SOURCE.relative_to(Path(__file__).resolve().parents[1]).as_posix(),
        )

    def test_source_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["source_commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "SOURCE_LINEAGE_MISMATCH"):
            _validate_decoded_receipt(changed, "semantic-test")

    def test_missing_proof_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["pairs"][0]["proof_refs"] = []
        with self.assertRaisesRegex(ValueError, "PAIR_PROOF_REFERENCES_INCOMPLETE"):
            _validate_decoded_receipt(changed, "semantic-test")

    def test_external_effect_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["external_effects"] = 1
        with self.assertRaisesRegex(ValueError, "EXTERNAL_EFFECT_PRESENT"):
            _validate_decoded_receipt(changed, "semantic-test")

    def test_insufficient_pairs_are_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["pairs"] = changed["pairs"][:29]
        with self.assertRaisesRegex(ValueError, "PAIR_COUNT_MISMATCH"):
            _validate_decoded_receipt(changed, "semantic-test")

    def test_attempted_stable_promotion_is_rejected(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["campaign"]["stable_promotion_allowed"] = True
        with self.assertRaisesRegex(ValueError, "STABLE_PROMOTION_MUST_REMAIN_DISABLED"):
            _validate_decoded_receipt(changed, "semantic-test")

    def test_any_byte_mutation_is_rejected_before_semantics(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["host"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "RECEIPT_HASH_MISMATCH"):
            admit_observed_campaign(encoded(changed))


if __name__ == "__main__":
    unittest.main()
