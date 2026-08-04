from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from authority_snapshot import AuthorityDomainLease, build_authority_snapshot
from authority_snapshot_acceptance import AuthoritySnapshotAcceptanceLedger
from authority_snapshot_control_plane import (
    AuthoritySnapshotCommercialControlPlane,
    REQUIRED_SCOPE,
)
from governed_commercial_assurance import LIVE_AUTHORITY_CLASS


NOW = "2026-08-04T07:00:00Z"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def lease(domain: str, observed_at: str, evidence: str) -> AuthorityDomainLease:
    scope = {
        "owner_decision": ("owner_identity_verification", "decision_receipt_issue"),
        "payment_provider": ("settlement_readback", "receipt_verification"),
        "customer_market": ("customer_identity", "outcome_evidence"),
    }[domain]
    return AuthorityDomainLease(
        domain=domain,
        state="FRESH_VERIFIED",
        authority_class=LIVE_AUTHORITY_CLASS,
        provider=f"provider-{domain}",
        locator=f"provider://{domain}/{evidence}",
        observed_at=observed_at,
        scope=scope,
        evidence_sha256=sha(evidence),
        max_age_seconds=86400,
    ).with_hash()


def snapshot(
    sequence: int,
    *,
    generated_at: str,
    expires_at: str,
    source_head: str,
    snapshot_id: str | None = None,
):
    return build_authority_snapshot(
        snapshot_id=snapshot_id or f"AO-AUTH-SNAPSHOT-{sequence}",
        generated_at=generated_at,
        expires_at=expires_at,
        source_projection_sha256=sha(f"projection-{sequence}-{source_head}"),
        source_ledger_head=sha(source_head),
        source_ledger_integrity=True,
        domains=(
            lease("owner_decision", generated_at, f"owner-{sequence}"),
            lease("payment_provider", generated_at, f"payment-{sequence}"),
            lease("customer_market", generated_at, f"customer-{sequence}"),
        ),
    )


class AuthoritySnapshotAcceptanceLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def validator(self, value):
        from authority_snapshot import CommercialAuthoritySnapshotValidator

        return CommercialAuthoritySnapshotValidator(value)

    def accept(self, ledger, value):
        return ledger.accept(
            value,
            self.validator(value),
            required_scope=REQUIRED_SCOPE,
            now=NOW,
        )

    def test_first_snapshot_is_accepted_and_restart_is_idempotent(self) -> None:
        value = snapshot(
            1,
            generated_at="2026-08-04T04:00:00Z",
            expires_at="2026-08-04T10:00:00Z",
            source_head="head-a",
        )
        ledger = AuthoritySnapshotAcceptanceLedger(self.root)
        first = self.accept(ledger, value)
        self.assertEqual(first["sequence"], 1)

        restarted = AuthoritySnapshotAcceptanceLedger(self.root)
        second = self.accept(restarted, value)
        self.assertEqual(second["entry_sha256"], first["entry_sha256"])
        self.assertEqual(len(restarted.entries), 1)

    def test_older_still_valid_snapshot_is_rejected_after_newer_acceptance(self) -> None:
        older = snapshot(
            1,
            generated_at="2026-08-04T04:00:00Z",
            expires_at="2026-08-04T10:00:00Z",
            source_head="head-a",
        )
        newer = snapshot(
            2,
            generated_at="2026-08-04T05:00:00Z",
            expires_at="2026-08-04T11:00:00Z",
            source_head="head-b",
        )
        ledger = AuthoritySnapshotAcceptanceLedger(self.root)
        self.accept(ledger, older)
        self.accept(ledger, newer)

        decision = ledger.preview(
            older,
            self.validator(older),
            required_scope=REQUIRED_SCOPE,
            now=NOW,
        )
        self.assertFalse(decision.valid)
        self.assertIn("AUTHORITY_SNAPSHOT_ROLLBACK_DETECTED", decision.reasons)

    def test_equal_generation_with_different_hash_is_equivocation(self) -> None:
        first = snapshot(
            1,
            generated_at="2026-08-04T05:00:00Z",
            expires_at="2026-08-04T11:00:00Z",
            source_head="head-a",
        )
        conflicting = snapshot(
            2,
            generated_at="2026-08-04T05:00:00Z",
            expires_at="2026-08-04T11:30:00Z",
            source_head="head-b",
        )
        ledger = AuthoritySnapshotAcceptanceLedger(self.root)
        self.accept(ledger, first)
        with self.assertRaisesRegex(
            PermissionError, "AUTHORITY_SNAPSHOT_EQUIVOCATION_DETECTED"
        ):
            self.accept(ledger, conflicting)

    def test_reuse_of_superseded_source_ledger_head_is_rejected(self) -> None:
        first = snapshot(
            1,
            generated_at="2026-08-04T04:00:00Z",
            expires_at="2026-08-04T10:00:00Z",
            source_head="head-a",
        )
        second = snapshot(
            2,
            generated_at="2026-08-04T05:00:00Z",
            expires_at="2026-08-04T11:00:00Z",
            source_head="head-b",
        )
        rollback = snapshot(
            3,
            generated_at="2026-08-04T06:00:00Z",
            expires_at="2026-08-04T12:00:00Z",
            source_head="head-a",
        )
        ledger = AuthoritySnapshotAcceptanceLedger(self.root)
        self.accept(ledger, first)
        self.accept(ledger, second)
        with self.assertRaisesRegex(
            PermissionError, "SOURCE_LEDGER_HEAD_ROLLBACK_DETECTED"
        ):
            self.accept(ledger, rollback)

    def test_ledger_tampering_fails_closed_on_restart(self) -> None:
        value = snapshot(
            1,
            generated_at="2026-08-04T04:00:00Z",
            expires_at="2026-08-04T10:00:00Z",
            source_head="head-a",
        )
        ledger = AuthoritySnapshotAcceptanceLedger(self.root)
        self.accept(ledger, value)

        line = json.loads(ledger.path.read_text(encoding="utf-8"))
        line["snapshot_id"] = "TAMPERED"
        ledger.path.write_text(json.dumps(line) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "ledger hash invalid"):
            AuthoritySnapshotAcceptanceLedger(self.root)


class AuthoritySnapshotAntiRollbackControlPlaneTests(unittest.TestCase):
    def test_canonical_control_plane_persists_acceptance_without_external_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            value = snapshot(
                1,
                generated_at="2026-08-04T04:00:00Z",
                expires_at="2026-08-04T10:00:00Z",
                source_head="head-a",
            )
            plane = AuthoritySnapshotCommercialControlPlane(
                temporary,
                authority_snapshot=value,
                authority_profile="LIVE_PROVIDER_AUTHORITY",
            )
            receipt = plane.accept_authority_snapshot(now=NOW)
            self.assertEqual(receipt["event"], "AUTHORITY_SNAPSHOT_ACCEPTED")

            readback = plane.governed_authority_readback()
            acceptance = readback["authority_snapshot"]["acceptance"]
            self.assertTrue(acceptance["anti_rollback_enforced"])
            self.assertEqual(acceptance["entries"], 1)
            self.assertEqual(readback["revenue"]["live_verified_revenue_events"], 0)


if __name__ == "__main__":
    unittest.main()
