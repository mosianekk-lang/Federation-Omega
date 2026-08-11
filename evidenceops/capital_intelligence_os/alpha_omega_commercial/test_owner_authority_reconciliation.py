from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from owner_authority_reconciliation import (
    FAILED,
    STATUS,
    verify_owner_authority_programme_reconciliation,
)


class OwnerAuthorityProgrammeReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.programme = json.loads(Path("programme.json").read_text(encoding="utf-8"))
        self.checkpoint = json.loads(
            Path("owner_authority_programme_checkpoint.json").read_text(encoding="utf-8")
        )
        self.contract = json.loads(
            Path("owner_authority_receipt_contract.json").read_text(encoding="utf-8")
        )
        self.authority_manifest = json.loads(
            Path("../sol_61_runtime/canonical_live_authority_manifest.json").read_text(encoding="utf-8")
        )

    def verify(self, programme=None, checkpoint=None, contract=None, authority_manifest=None):
        return verify_owner_authority_programme_reconciliation(
            programme or self.programme,
            checkpoint or self.checkpoint,
            contract or self.contract,
            authority_manifest or self.authority_manifest,
        )

    def test_verified_reconciliation(self) -> None:
        result = self.verify()
        self.assertEqual(result["status"], STATUS)
        self.assertTrue(all(result["checks"].values()))
        self.assertFalse(any(result["external_gates"].values()))
        self.assertEqual(result["programme_projection"]["C13"]["verified_revenue_events"], 0)
        self.assertFalse(result["programme_projection"]["C15"]["full_commercial_maturity"])

    def test_owner_authority_promotion_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["owner_authority"]["state"] = "FRESH_VERIFIED"
        result = self.verify(checkpoint=checkpoint)
        self.assertEqual(result["status"], FAILED)
        self.assertFalse(result["checks"]["owner_reserved_authority_preserved"])

    def test_external_gate_promotion_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["external_gates"]["signed_customer_contract"] = True
        result = self.verify(checkpoint=checkpoint)
        self.assertEqual(result["status"], FAILED)
        self.assertFalse(result["checks"]["external_gates_unchanged"])

    def test_revenue_claim_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["truth_boundary"]["verified_revenue_events"] = 1
        result = self.verify(checkpoint=checkpoint)
        self.assertEqual(result["status"], FAILED)
        self.assertFalse(result["checks"]["zero_revenue_preserved"])

    def test_cloud_run_claim_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["truth_boundary"]["cloud_run_operation_proven"] = True
        result = self.verify(checkpoint=checkpoint)
        self.assertEqual(result["status"], FAILED)
        self.assertFalse(result["checks"]["cloud_operation_not_claimed"])

    def test_provider_proof_tamper_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["provider_proof"]["artifact_digest"] = "sha256:" + "0" * 64
        result = self.verify(checkpoint=checkpoint)
        self.assertEqual(result["status"], FAILED)
        self.assertFalse(result["checks"]["provider_proof_exact"])

    def test_drive_readback_removal_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.checkpoint)
        checkpoint["google_drive_readback"]["readback_verified"] = False
        result = self.verify(checkpoint=checkpoint)
        self.assertEqual(result["status"], FAILED)
        self.assertFalse(result["checks"]["drive_release_readback_preserved"])

    def test_dependency_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["stages"][12]["depends_on"] = ["C15"]
        result = self.verify(programme=programme)
        self.assertEqual(result["status"], FAILED)
        self.assertFalse(result["checks"]["dependency_order_valid"])


if __name__ == "__main__":
    unittest.main()
