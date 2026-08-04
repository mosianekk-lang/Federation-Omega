from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from alpha_omega_commercial.institution_reconciliation import (
    ReconciliationError,
    digest,
    load_json,
    verify_institution_reconciliation,
)
from alpha_omega_commercial.prove_institution_reconciliation import (
    COMMERCIAL_ROOT,
    INSTITUTION_ROOT,
    build_proof,
)


class InstitutionReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.commercial_programme = load_json(COMMERCIAL_ROOT / "programme.json")
        cls.release = load_json(
            COMMERCIAL_ROOT / "governed_authority_release_receipt.json"
        )
        cls.governed_checkpoint = load_json(
            COMMERCIAL_ROOT / "governed_authority_checkpoint.json"
        )
        cls.institution_programme = load_json(INSTITUTION_ROOT / "programme.json")
        cls.institution_checkpoint = load_json(
            INSTITUTION_ROOT / "checkpoint_20260803.json"
        )

    def reconcile(
        self,
        *,
        commercial_programme=None,
        release=None,
        governed_checkpoint=None,
        institution_programme=None,
        institution_checkpoint=None,
    ):
        return verify_institution_reconciliation(
            copy.deepcopy(commercial_programme or self.commercial_programme),
            copy.deepcopy(release or self.release),
            copy.deepcopy(governed_checkpoint or self.governed_checkpoint),
            copy.deepcopy(institution_programme or self.institution_programme),
            copy.deepcopy(institution_checkpoint or self.institution_checkpoint),
        )

    def test_current_state_reconciles_without_promoting_external_gates(self) -> None:
        result = self.reconcile()
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(
            result["status"],
            "COMMERCIAL_INSTITUTION_RECONCILIATION_VERIFIED_SCOPE_BOUNDARIES_PRESERVED",
        )
        self.assertEqual(result["commercial_projection"]["verified_live_revenue_events"], 0)
        self.assertFalse(result["commercial_projection"]["full_commercial_maturity"])
        self.assertEqual(
            result["scope_projection"]["institution_v3_google_drive_publication"],
            "UNVERIFIED_SCOPE_HELD",
        )

    def test_proof_is_persisted_and_hash_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            receipt = build_proof(path)
            readback = json.loads(path.read_text(encoding="utf-8"))
            receipt_hash = readback.pop("receipt_sha256")
            self.assertEqual(receipt_hash, digest(readback))
            self.assertEqual(receipt["receipt_sha256"], receipt_hash)

    def test_external_gate_promotion_is_rejected(self) -> None:
        release = copy.deepcopy(self.release)
        release["external_gates"]["customer_demand"] = True
        self._rehash_release(release)
        with self.assertRaisesRegex(ReconciliationError, "external maturity gate"):
            self.reconcile(release=release)

    def test_unverified_revenue_claim_is_rejected(self) -> None:
        release = copy.deepcopy(self.release)
        release["truth_boundary"]["verified_live_revenue_events"] = 1
        self._rehash_release(release)
        with self.assertRaisesRegex(ReconciliationError, "live revenue"):
            self.reconcile(release=release)

    def test_cloud_run_promotion_is_rejected(self) -> None:
        release = copy.deepcopy(self.release)
        release["truth_boundary"]["cloud_run_operation_proven"] = True
        self._rehash_release(release)
        with self.assertRaisesRegex(ReconciliationError, "Cloud Run"):
            self.reconcile(release=release)

    def test_cross_scope_drive_promotion_is_rejected(self) -> None:
        checkpoint = copy.deepcopy(self.institution_checkpoint)
        checkpoint["provider_authority"]["google_drive_write"] = "FRESH_VERIFIED"
        with self.assertRaisesRegex(ReconciliationError, "v3 institution publication"):
            self.reconcile(institution_checkpoint=checkpoint)

    def test_commercial_dependency_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.commercial_programme)
        programme["stages"][3]["depends_on"] = ["C15"]
        with self.assertRaisesRegex(ReconciliationError, "commercial dependency order"):
            self.reconcile(commercial_programme=programme)

    def test_institution_dependency_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.institution_programme)
        programme["sequence"][4]["depends_on"] = ["P15"]
        with self.assertRaisesRegex(ReconciliationError, "institution dependency order"):
            self.reconcile(institution_programme=programme)

    def test_release_hash_tampering_is_rejected(self) -> None:
        release = copy.deepcopy(self.release)
        release["implementation"]["canonical_class"] = "LegacyCommercialControlPlane"
        with self.assertRaisesRegex(ReconciliationError, "receipt hash"):
            self.reconcile(release=release)

    def test_owner_authority_drift_is_rejected(self) -> None:
        release = copy.deepcopy(self.release)
        release["owner_authority"]["contracts"] = "AUTOMATED"
        self._rehash_release(release)
        checkpoint = copy.deepcopy(self.governed_checkpoint)
        checkpoint["release_receipt"]["receipt_sha256"] = release["receipt_sha256"]
        with self.assertRaisesRegex(ReconciliationError, "owner-reserved authority"):
            self.reconcile(release=release, governed_checkpoint=checkpoint)

    @staticmethod
    def _rehash_release(release: dict) -> None:
        release.pop("receipt_sha256", None)
        release["receipt_sha256"] = digest(release)


if __name__ == "__main__":
    unittest.main()
