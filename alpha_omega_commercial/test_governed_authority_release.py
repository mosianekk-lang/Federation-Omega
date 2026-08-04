from __future__ import annotations

import copy
import unittest
from pathlib import Path

from governed_authority_release import load, verify_release


ROOT = Path(__file__).resolve().parent


class GovernedAuthorityReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = load(ROOT / "governed_authority_release_receipt.json")
        self.checkpoint = load(ROOT / "governed_authority_checkpoint.json")
        self.programme = load(ROOT / "programme.json")

    def verify(self, receipt=None, checkpoint=None, programme=None):
        return verify_release(
            receipt or self.receipt,
            checkpoint or self.checkpoint,
            programme or self.programme,
        )

    def test_release_reconciliation_is_verified(self) -> None:
        result = self.verify()
        self.assertEqual(
            result["status"],
            "GOVERNED_AUTHORITY_RELEASE_RECONCILIATION_VERIFIED",
        )
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["verified_live_revenue_events"], 0)
        self.assertFalse(result["full_commercial_maturity"])

    def test_receipt_hash_tamper_is_rejected(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["google_drive_release"]["exported_text_size_bytes"] += 1
        self.assertFalse(self.verify(receipt=receipt)["checks"]["receipt_hash_valid"])

    def test_provider_artifact_drift_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["provider_proof"]["artifact_id"] += 1
        result = self.verify(checkpoint=checkpoint)
        self.assertFalse(result["checks"]["checkpoint_provider_proof_matches"])

    def test_drive_publication_drift_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["google_drive_release"]["shared"] = True
        result = self.verify(checkpoint=checkpoint)
        self.assertFalse(result["checks"]["checkpoint_drive_matches"])

    def test_external_gate_promotion_is_rejected(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["external_gates"]["customer_demand"] = True
        result = self.verify(receipt=receipt)
        self.assertFalse(result["checks"]["external_gates_all_open"])

    def test_revenue_claim_is_rejected(self) -> None:
        receipt = copy.deepcopy(self.receipt)
        receipt["truth_boundary"]["verified_live_revenue_events"] = 1
        result = self.verify(receipt=receipt)
        self.assertFalse(result["checks"]["zero_revenue_truth_preserved"])

    def test_owner_authority_drift_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["owner_authority"]["contracts"] = "AUTOMATED"
        result = self.verify(checkpoint=checkpoint)
        self.assertFalse(result["checks"]["owner_authority_preserved"])


if __name__ == "__main__":
    unittest.main()
