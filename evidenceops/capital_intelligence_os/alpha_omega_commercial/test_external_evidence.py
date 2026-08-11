from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from external_evidence import EvidenceEnvelope, ExternalEvidenceAdmissionController
from owner_authority import OwnerDecisionReceipt


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
        "owner_decision": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    }
    states.update(overrides)
    return {key: {"state": value} for key, value in states.items()}


def owner_receipt(
    *,
    receipt_id: str,
    gate: str,
    evidence_id: str,
    evidence_content_sha256: str,
    decision: str = "APPROVE",
    owner_id: str = "Kim Kagiso Mosiane",
    provider_class: str = "OWNER_PROVIDER_NATIVE",
    issued_at: str = "2026-08-03T18:10:00Z",
    expires_at: str = "2026-08-04T18:10:00Z",
) -> OwnerDecisionReceipt:
    return OwnerDecisionReceipt(
        receipt_id=receipt_id,
        owner_id=owner_id,
        gate=gate,
        evidence_id=evidence_id,
        evidence_content_sha256=evidence_content_sha256,
        decision=decision,
        issued_at=issued_at,
        expires_at=expires_at,
        provider="owner-authority-provider",
        locator=f"provider://owner-decisions/{receipt_id}",
        provider_class=provider_class,
        nonce=f"nonce-{receipt_id}",
    ).with_hash()


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

    def payment(self, **changes) -> EvidenceEnvelope:
        data = {
            "evidence_id": "payment-002",
            "gate": "payment_provider_revenue",
            "provider": "payment-provider",
            "locator": "provider://payment/receipt-002",
            "observed_at": "2026-08-03T18:00:00Z",
            "content_sha256": sha("payment-002"),
            "evidence_class": "EXTERNAL_PROVIDER_NATIVE",
            "claims": {"settled": True, "currency": "ZAR", "amount": 1000.0},
            "owner_confirmed": False,
            "owner_decision_receipt_id": None,
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

    def test_rejects_blocked_payment_provider_and_missing_owner_receipt(self) -> None:
        decision = self.controller.admit(self.payment(evidence_id="payment-001"), now=NOW)
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("PROVIDER_AUTHORITY_NOT_VERIFIED:payment_provider", decision["reasons"])
        self.assertIn("OWNER_DECISION_RECEIPT_REQUIRED", decision["reasons"])

    def test_boolean_owner_confirmation_cannot_bypass_owner_authority(self) -> None:
        controller = ExternalEvidenceAdmissionController(
            self.root / "boolean-bypass",
            authority(payment_provider="FRESH_VERIFIED", owner_decision="FRESH_VERIFIED"),
        )
        decision = controller.admit(self.payment(owner_confirmed=True), now=NOW)
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("BOOLEAN_OWNER_CONFIRMATION_NOT_ACCEPTED", decision["reasons"])
        self.assertIn("OWNER_DECISION_RECEIPT_REQUIRED", decision["reasons"])

    def test_valid_owner_receipt_admits_payment_only_with_both_authorities(self) -> None:
        receipt = owner_receipt(
            receipt_id="owner-payment-002",
            gate="payment_provider_revenue",
            evidence_id="payment-002",
            evidence_content_sha256=sha("payment-002"),
        )
        controller = ExternalEvidenceAdmissionController(
            self.root / "fresh-payment",
            authority(payment_provider="FRESH_VERIFIED", owner_decision="FRESH_VERIFIED"),
            owner_receipts={receipt.receipt_id: receipt},
        )
        decision = controller.admit(
            self.payment(owner_decision_receipt_id=receipt.receipt_id),
            now=NOW,
        )
        self.assertEqual(decision["status"], "ADMITTED")
        self.assertEqual(decision["owner_decision_receipt_sha256"], receipt.receipt_sha256)
        self.assertEqual(
            controller.project_maturity()["consumed_owner_receipts"][receipt.receipt_id],
            "payment-002",
        )

    def test_rejects_forged_or_mismatched_owner_receipt(self) -> None:
        receipt = owner_receipt(
            receipt_id="owner-payment-forged",
            gate="payment_provider_revenue",
            evidence_id="different-payment",
            evidence_content_sha256=sha("different"),
        )
        controller = ExternalEvidenceAdmissionController(
            self.root / "forged-payment",
            authority(payment_provider="FRESH_VERIFIED", owner_decision="FRESH_VERIFIED"),
            owner_receipts={receipt.receipt_id: receipt},
        )
        decision = controller.admit(
            self.payment(owner_decision_receipt_id=receipt.receipt_id),
            now=NOW,
        )
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("OWNER_DECISION_EVIDENCE_ID_MISMATCH", decision["reasons"])
        self.assertIn("OWNER_DECISION_EVIDENCE_HASH_MISMATCH", decision["reasons"])

    def test_rejects_expired_owner_receipt(self) -> None:
        receipt = owner_receipt(
            receipt_id="owner-payment-expired",
            gate="payment_provider_revenue",
            evidence_id="payment-002",
            evidence_content_sha256=sha("payment-002"),
            issued_at="2026-07-01T00:00:00Z",
            expires_at="2026-07-02T00:00:00Z",
        )
        controller = ExternalEvidenceAdmissionController(
            self.root / "expired-payment",
            authority(payment_provider="FRESH_VERIFIED", owner_decision="FRESH_VERIFIED"),
            owner_receipts={receipt.receipt_id: receipt},
        )
        decision = controller.admit(
            self.payment(owner_decision_receipt_id=receipt.receipt_id),
            now=NOW,
        )
        self.assertEqual(decision["status"], "REJECTED")
        self.assertIn("OWNER_DECISION_EXPIRED", decision["reasons"])

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
