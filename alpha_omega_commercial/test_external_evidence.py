from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from external_evidence import EvidenceEnvelope, ExternalEvidenceAdmissionController


NOW = "2026-08-03T18:50:00Z"


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def authority(**overrides: str) -> dict[str, dict[str, str]]:
    states = {
        "customer_market": "FRESH_VERIFIED",
        "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        "cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        "external_attestation": "UNVERIFIED",
        "partner_market": "MARKET_PROOF_REQUIRED",
        "live_cloud_operations": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    }
    states.update(overrides)
    return {key: {"state": value} for key, value in states.items()}


class ExternalEvidenceAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.controller = ExternalEvidenceAdmissionController(self.root, authority())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def demand(self, **changes) -> EvidenceEnvelope:
        data = {
            "evidence_id": "demand-001",
            "gate": "customer_demand",
            "provider": "customer-record-system",
            "locator": "provider://customer/demand-001",
            "observed_at": "2026-08-03T18:00:00Z",
            "content_sha256": sha("demand-001"),
            "evidence_class": "EXTERNAL_PROVIDER_NATIVE",
            "claims": {"customer_identity_verified": True, "price_accepted": True},
            "owner_confirmed": False,
        }
        data.update(changes)
        return EvidenceEnvelope(**data)

    def test_admits_complete_external_provider_native_demand_evidence(self) -> None:
        decision = self.controller.admit(self.demand(), now=NOW)
        self.assertEqual(decision["status"], "ADMITTED")
        projection = self.controller.project_maturity()
        self.assertTrue(projection["external_gates"]["customer_demand"])
        self.assertFalse(projection["full_commercial_maturity"])
        self.assertTrue(projection["ledger_integrity"])

    def test_rejects_synthetic_or_internal_evidence(self) -> None:
        decision = self.controller.admit(
            self.demand(evidence_class="MOCK_CONFORMANCE"), now=NOW
        )
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("NON_EXTERNAL_OR_SYNTHETIC_EVIDENCE", decision["reasons"])
        self.assertFalse(any(self.controller.project_maturity()["external_gates"].values()))

    def test_rejects_blocked_payment_provider_and_missing_owner_confirmation(self) -> None:
        payment = EvidenceEnvelope(
            evidence_id="payment-001",
            gate="payment_provider_revenue",
            provider="payment-provider",
            locator="provider://payment/receipt-001",
            observed_at="2026-08-03T18:00:00Z",
            content_sha256=sha("payment-001"),
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={"settled": True, "currency": "ZAR", "amount": 1000.0},
            owner_confirmed=False,
        )
        decision = self.controller.admit(payment, now=NOW)
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("PROVIDER_AUTHORITY_NOT_VERIFIED:payment_provider", decision["reasons"])
        self.assertIn("OWNER_CONFIRMATION_REQUIRED", decision["reasons"])

    def test_owner_confirmed_payment_is_admitted_only_with_fresh_authority(self) -> None:
        controller = ExternalEvidenceAdmissionController(
            self.root / "fresh-payment",
            authority(payment_provider="FRESH_VERIFIED"),
        )
        payment = EvidenceEnvelope(
            evidence_id="payment-002",
            gate="payment_provider_revenue",
            provider="payment-provider",
            locator="provider://payment/receipt-002",
            observed_at="2026-08-03T18:00:00Z",
            content_sha256=sha("payment-002"),
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={"settled": True, "currency": "ZAR", "amount": 1000.0},
            owner_confirmed=True,
        )
        self.assertEqual(controller.admit(payment, now=NOW)["status"], "ADMITTED")

    def test_rejects_cloud_claim_without_provider_authority(self) -> None:
        cloud = EvidenceEnvelope(
            evidence_id="cloud-001",
            gate="live_cloud_provider",
            provider="cloud-run",
            locator="provider://cloud-run/service/revision",
            observed_at="2026-08-03T18:00:00Z",
            content_sha256=sha("cloud-001"),
            evidence_class="EXTERNAL_PROVIDER_NATIVE",
            claims={
                "deployment_id": "revision-001",
                "readback": True,
                "health": True,
                "persistence": True,
                "rollback": True,
            },
        )
        decision = self.controller.admit(cloud, now=NOW)
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("PROVIDER_AUTHORITY_NOT_VERIFIED:cloud_run", decision["reasons"])

    def test_idempotent_replay_and_conflicting_duplicate(self) -> None:
        first = self.controller.admit(self.demand(), now=NOW)
        second = self.controller.admit(self.demand(), now=NOW)
        self.assertEqual(first, second)
        conflict = self.controller.admit(
            self.demand(content_sha256=sha("different")), now=NOW
        )
        self.assertEqual(conflict["status"], "REJECTED")
        self.assertEqual(conflict["reasons"], ["EVIDENCE_ID_CONFLICT"])
        restarted = ExternalEvidenceAdmissionController(self.root, authority())
        self.assertTrue(restarted.project_maturity()["external_gates"]["customer_demand"])
        self.assertTrue(restarted.verify_ledger())

    def test_stale_evidence_is_rejected(self) -> None:
        decision = self.controller.admit(
            self.demand(observed_at="2025-01-01T00:00:00Z"), now=NOW
        )
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("EVIDENCE_STALE", decision["reasons"])


if __name__ == "__main__":
    unittest.main()
