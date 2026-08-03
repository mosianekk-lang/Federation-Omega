from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from programme_integrity import verify_programme_register


class ProgrammeRegisterIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.programme = json.loads(Path("programme.json").read_text(encoding="utf-8"))
        self.maturity = {
            "canonical_status": "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN",
            "technical_reference_ready": True,
            "full_commercial_maturity": False,
            "external_gates": {
                "customer_demand": False,
                "enterprise_attestation": False,
                "external_case_study": False,
                "live_cloud_provider": False,
                "partner_adoption": False,
                "payment_provider_revenue": False,
                "production_scale": False,
                "signed_customer_contract": False,
            },
        }
        self.integrity = {
            "status": "CANONICAL_RECEIPT_INTEGRITY_VERIFIED",
            "integrity_receipt_sha256": "1908449a171078d4592199cddabdc8187df2d2069776df838a0b027e56f6a7e0",
            "checks": {
                "embedded_c15_ready": True,
                "embedded_maturity_matches_final": True,
                "ledger_chain_valid": True,
                "package_hash_valid": True,
                "rollback_snapshot_available": True,
                "state_readback_matches_package": True,
                "top_level_maturity_matches_final": True,
                "top_level_package_matches_state": True,
                "top_receipt_hash_valid": True,
            },
        }
        self.receipt = {
            "canonical_receipt_integrity": {"status": "CANONICAL_RECEIPT_INTEGRITY_VERIFIED"},
            "stages": {"C13": {"proof": {"verified_revenue_events": 0}}},
            "truth_boundaries": {"cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY"},
        }

    def verify(self, programme=None, integrity=None, maturity=None, receipt=None):
        return verify_programme_register(
            programme or self.programme,
            integrity or self.integrity,
            maturity or self.maturity,
            receipt or self.receipt,
        )

    def test_verified_programme_register(self) -> None:
        result = self.verify()
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_VERIFIED")
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["provider_authority_freshness"], "PROVIDER_AUTHORITY_FRESHNESS_RECONCILIATION_VERIFIED")

    def test_stale_integrity_gate_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["canonical_receipt_integrity"] = "C15_SELF_CONSISTENCY_READBACK_AND_ROLLBACK_PROOF_REQUIRED"
        result = self.verify(programme=programme)
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_FAILED")
        self.assertFalse(result["checks"]["canonical_integrity_status_matches"])

    def test_unproven_external_gate_is_rejected(self) -> None:
        maturity = copy.deepcopy(self.maturity)
        maturity["external_gates"]["customer_demand"] = True
        result = self.verify(maturity=maturity)
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_FAILED")
        self.assertFalse(result["checks"]["external_gate_evidence_consistent"])

    def test_dependency_order_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["stages"][2]["depends_on"] = ["C04"]
        result = self.verify(programme=programme)
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_FAILED")
        self.assertFalse(result["checks"]["dependency_order_valid"])

    def test_external_evidence_admission_status_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["external_evidence_admission"]["status"] = "PENDING"
        result = self.verify(programme=programme)
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_FAILED")
        self.assertFalse(result["checks"]["external_evidence_admission_verified"])

    def test_provider_authority_scope_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["external_evidence_admission"]["provider_authority"]["cloud_run"] = "FRESH_VERIFIED"
        result = self.verify(programme=programme)
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_FAILED")
        self.assertFalse(result["checks"]["provider_authority_scopes_precise"])

    def test_provider_authority_freshness_drift_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["provider_authority_freshness"]["latest_verified"]["google_drive_document_release"]["content_sha256"] = "bad"
        result = self.verify(programme=programme)
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_FAILED")
        self.assertFalse(result["checks"]["authority_freshness_operational_evidence_complete"])

    def test_blocked_provider_promotion_is_rejected(self) -> None:
        programme = copy.deepcopy(self.programme)
        programme["provider_authority_freshness"]["blocked_or_unverified"]["cloud_run"] = "FRESH_VERIFIED"
        result = self.verify(programme=programme)
        self.assertEqual(result["status"], "PROGRAMME_REGISTER_INTEGRITY_FAILED")
        self.assertFalse(result["checks"]["authority_freshness_blocked_domains_preserved"])


if __name__ == "__main__":
    unittest.main()
