from __future__ import annotations

import unittest

from canonical_authority_reconciliation import AuthorityReconciliationError, project_programme, reconcile


def fixtures():
    programme = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "owner_reserved_authority": [
            "financial commitments", "contracts", "external communications",
            "consequential releases", "revenue recognition confirmation",
        ],
        "external_gate_evidence": {},
        "external_evidence_admission": {"provider_authority": {
            "cloud_run": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
            "live_cloud_operations": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED",
        }},
        "live_provider_expansion": {"provider_states": {"google_cloud_run": "PROVIDER_BLOCKED_WIF_TOKEN_EXCHANGE_FAILED"}},
        "stages": [
            {"id": f"C{i:02d}", "depends_on": [] if i == 1 else [f"C{i-1:02d}"], "status": "X", "maturity_gate": "X"}
            for i in range(1, 16)
        ],
    }
    requirements = {"requirements": [{
        "domain": "cloud_run",
        "required_proofs": ["provider_identity", "execution", "readback", "health", "persistence", "rollback"],
    }]}
    manifest = {
        "manifest_id": "FO-CLAM-2026-08-04-v1",
        "cloud_run": {
            "project_id": "sov-hybrid-suite", "region": "africa-south1",
            "service": "federation-omega-operator", "path": "/execute",
            "candidate_identities": ["fo-automation-agent", "fo-operator"],
            "required_sequence": ["AUTHENTICATED_STATUS", "READ_CLOUD_RUN_SERVICE", "REVERSIBLE_CANARY", "SEMANTIC_READBACK", "ROLLBACK_RECEIPT"],
            "promotion_receipts": ["provider_revision", "request_id", "authenticated_principal", "response_status", "response_body_sha256", "readback_match", "rollback_receipt"],
            "status": "CONTROL_PLANE_PRESENT_LIVE_INVOCATION_UNPROVEN",
        },
        "certified_reversible_surfaces": ["github", "google_drive"],
    }
    register = {"providers": {
        "github": {"status": "VERIFIED_OPERATIONAL"},
        "google_drive": {"status": "VERIFIED_OPERATIONAL"},
    }}
    workflow = """env:\n  PROJECT_ID: sov-hybrid-suite\n  REGION: africa-south1\n  SERVICE: federation-omega-operator\n  SERVICE_PATH: /execute\n"""
    return programme, requirements, manifest, register, workflow


class ReconciliationTests(unittest.TestCase):
    def test_canonical_route_is_aligned_without_live_claim(self):
        receipt = reconcile(*fixtures())
        self.assertEqual(receipt["status"], "CANONICAL_PROVIDER_ROUTE_ALIGNED_IDENTITY_AUTHORITY_UNAVAILABLE")
        self.assertFalse(receipt["cloud_run"]["live_invocation_proven"])
        self.assertTrue(all(receipt["gates"].values()))

    def test_legacy_service_drift_is_rejected(self):
        values = list(fixtures())
        values[-1] = values[-1].replace("federation-omega-operator", "fo-transcription-bridge")
        with self.assertRaises(AuthorityReconciliationError):
            reconcile(*values)

    def test_unproved_live_claim_is_rejected(self):
        values = list(fixtures())
        values[0]["external_evidence_admission"]["provider_authority"]["cloud_run"] = "VERIFIED_LIVE"
        with self.assertRaises(AuthorityReconciliationError):
            reconcile(*values)

    def test_owner_authority_cannot_be_weakened(self):
        values = list(fixtures())
        values[0]["owner_reserved_authority"].remove("contracts")
        with self.assertRaises(AuthorityReconciliationError):
            reconcile(*values)

    def test_projection_changes_no_external_gate(self):
        programme, requirements, manifest, register, workflow = fixtures()
        receipt = reconcile(programme, requirements, manifest, register, workflow)
        projected = project_programme(programme, receipt)
        self.assertEqual(projected["external_gate_evidence"], {})
        self.assertFalse(projected["canonical_authority_reconciliation"]["full_commercial_maturity"])
        self.assertEqual(
            projected["external_evidence_admission"]["provider_authority"]["cloud_run"],
            "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
