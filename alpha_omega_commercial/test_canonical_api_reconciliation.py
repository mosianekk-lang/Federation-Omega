from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from alpha_omega_commercial import (
    IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
)
from canonical_api_reconciliation import verify_canonical_api_reconciliation


class CanonicalApiReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parent
        self.programme = json.loads((root / "programme.json").read_text(encoding="utf-8"))
        self.compatibility = json.loads(
            (root / "canonical_commercial_api.json").read_text(encoding="utf-8")
        )
        self.projection = json.loads(
            (root / "canonical_commercial_api_effective_v10.json").read_text(
                encoding="utf-8"
            )
        )
        self.release = json.loads(
            (root / "authority_action_idempotency_release_checkpoint.json").read_text(
                encoding="utf-8"
            )
        )
        self.institution = json.loads(
            (root / "institution_reconciliation_checkpoint.json").read_text(
                encoding="utf-8"
            )
        )

    def verify(self, *, programme=None, compatibility=None, projection=None, release=None, institution=None, package_class=None):
        return verify_canonical_api_reconciliation(
            programme or self.programme,
            compatibility or self.compatibility,
            projection or self.projection,
            release or self.release,
            institution or self.institution,
            package_class or IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane,
        )

    def test_verified_effective_v10_projection(self) -> None:
        result = self.verify()
        self.assertEqual(
            result["status"], "CANONICAL_API_EFFECTIVE_V10_PROVIDER_PROOF_VERIFIED"
        )
        self.assertEqual(result["checks_failed"], 0)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(
            result["effective_canonical_class"],
            "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane",
        )

    def test_dependency_order_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["stages"][2]["depends_on"] = ["C04"]
        result = self.verify(programme=programme)
        self.assertFalse(result["checks"]["programme_dependency_order"])
        self.assertGreater(result["checks_failed"], 0)

    def test_compatibility_anchor_rewrite_is_rejected(self) -> None:
        compatibility = copy.deepcopy(self.compatibility)
        compatibility["current_canonical_class"] = (
            "IdempotentCoordinatedAuthoritySnapshotCommercialControlPlane"
        )
        result = self.verify(compatibility=compatibility)
        self.assertFalse(result["checks"]["compatibility_descriptor_preserved"])

    def test_effective_class_drift_is_rejected(self) -> None:
        projection = copy.deepcopy(self.projection)
        projection["effective_api"]["canonical_class"] = "WrongControlPlane"
        result = self.verify(projection=projection)
        self.assertFalse(result["checks"]["effective_projection_exact"])
        self.assertFalse(result["checks"]["release_effective_api_matches"])

    def test_unsupported_exactly_once_claim_is_rejected(self) -> None:
        projection = copy.deepcopy(self.projection)
        projection["effective_api"]["idempotency_controls"][
            "distributed_provider_exactly_once_proven"
        ] = True
        projection["commercial_truth"][
            "distributed_provider_exactly_once_proven"
        ] = True
        result = self.verify(projection=projection)
        self.assertFalse(result["checks"]["idempotency_controls_exact"])
        self.assertFalse(result["checks"]["commercial_truth_preserved"])

    def test_external_gate_promotion_is_rejected(self) -> None:
        projection = copy.deepcopy(self.projection)
        projection["external_gates"]["customer_demand_and_price_acceptance"] = True
        result = self.verify(projection=projection)
        self.assertFalse(result["checks"]["external_gates_remain_false"])

    def test_drive_readback_loss_is_rejected(self) -> None:
        release = copy.deepcopy(self.release)
        release["google_drive_release"]["readback_verified"] = False
        result = self.verify(release=release)
        self.assertFalse(result["checks"]["release_drive_readback_bound"])

    def test_institution_scope_promotion_is_rejected(self) -> None:
        institution = copy.deepcopy(self.institution)
        institution["provider_scope"]["institution_v3_google_drive_publication"] = (
            "FRESH_VERIFIED"
        )
        result = self.verify(institution=institution)
        self.assertFalse(result["checks"]["institution_boundary_preserved"])

    def test_owner_authority_drift_is_rejected(self) -> None:
        projection = copy.deepcopy(self.projection)
        projection["owner_authority"]["contracts"] = "AUTOMATED"
        result = self.verify(projection=projection)
        self.assertFalse(result["checks"]["owner_authority_preserved"])


if __name__ == "__main__":
    unittest.main()
