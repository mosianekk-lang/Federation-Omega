from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from authority_snapshot import (
    AuthorityDomainLease,
    CommercialAuthoritySnapshotValidator,
    build_authority_snapshot,
    digest,
)
from authority_snapshot_control_plane import AuthoritySnapshotCommercialControlPlane
from governed_commercial_assurance import LIVE_AUTHORITY_CLASS
from owner_authority import OwnerDecisionReceipt


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_snapshot(now: datetime):
    generated = now - timedelta(minutes=5)
    expires = now + timedelta(hours=12)

    def lease(domain: str, scope: tuple[str, ...]) -> AuthorityDomainLease:
        return AuthorityDomainLease(
            domain=domain,
            state="FRESH_VERIFIED",
            authority_class=LIVE_AUTHORITY_CLASS,
            provider=f"provider-proof-{domain}",
            locator=f"proof://{domain}/receipt",
            observed_at=iso(generated),
            scope=scope,
            evidence_sha256=sha(f"provider-evidence-{domain}"),
            max_age_seconds=86400,
        ).with_hash()

    return build_authority_snapshot(
        snapshot_id="AO-COMMERCIAL-AUTHORITY-SNAPSHOT-PROOF",
        generated_at=iso(generated),
        expires_at=iso(expires),
        source_projection_sha256=sha("authority-freshness-projection"),
        source_ledger_head=sha("authority-freshness-ledger-head"),
        source_ledger_integrity=True,
        domains=(
            lease(
                "owner_decision",
                ("owner_identity_verification", "decision_receipt_issue"),
            ),
            lease(
                "payment_provider",
                ("settlement_readback", "receipt_verification"),
            ),
            lease(
                "customer_market",
                ("customer_identity", "outcome_evidence"),
            ),
        ),
    )


def owner_receipt(*, gate: str, evidence_id: str, content_sha256: str, now: datetime):
    return OwnerDecisionReceipt(
        receipt_id="OWNER-QUOTE-PROOF-1",
        owner_id="Kim Kagiso Mosiane",
        gate=gate,
        evidence_id=evidence_id,
        evidence_content_sha256=content_sha256,
        decision="APPROVE",
        issued_at=iso(now - timedelta(minutes=1)),
        expires_at=iso(now + timedelta(hours=1)),
        provider="provider-proof-owner-decision",
        locator="proof://owner-decision/receipt/1",
        provider_class="OWNER_PROVIDER_NATIVE",
        nonce="authority-snapshot-proof-nonce",
    ).with_hash()


def main() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_text = iso(now)
    snapshot = build_snapshot(now)
    checks: dict[str, bool] = {}

    owner_decision = CommercialAuthoritySnapshotValidator(snapshot).validate_domain(
        "owner_decision",
        required_scope=("owner_identity_verification", "decision_receipt_issue"),
        now=now_text,
    )
    checks["valid_owner_snapshot"] = owner_decision.valid

    tampered = snapshot.to_dict()
    tampered["domains"]["owner_decision"]["locator"] = "proof://tampered"
    tampered_decision = CommercialAuthoritySnapshotValidator(tampered).validate_domain(
        "owner_decision",
        required_scope=("owner_identity_verification", "decision_receipt_issue"),
        now=now_text,
    )
    checks["tamper_rejected"] = (
        not tampered_decision.valid
        and "SNAPSHOT_HASH_INVALID" in tampered_decision.reasons
        and "AUTHORITY_DOMAIN_HASH_INVALID" in tampered_decision.reasons
    )

    expired = build_authority_snapshot(
        snapshot_id="AO-COMMERCIAL-AUTHORITY-SNAPSHOT-EXPIRED",
        generated_at=iso(now - timedelta(hours=2)),
        expires_at=iso(now - timedelta(hours=1)),
        source_projection_sha256=sha("expired-projection"),
        source_ledger_head=sha("expired-ledger-head"),
        source_ledger_integrity=True,
        domains=snapshot.domains.values(),
    )
    expired_decision = CommercialAuthoritySnapshotValidator(expired).validate_domain(
        "owner_decision",
        now=now_text,
    )
    checks["expired_snapshot_rejected"] = (
        not expired_decision.valid and "SNAPSHOT_EXPIRED" in expired_decision.reasons
    )

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        raw = {
            "owner_decision": {
                "state": "FRESH_VERIFIED",
                "authority_class": LIVE_AUTHORITY_CLASS,
            }
        }
        raw_plane = AuthoritySnapshotCommercialControlPlane(
            root / "raw",
            authority=raw,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        raw_plane.create_lead("LEAD-RAW", "org", "inbound", "manual delay")
        raw_plane.create_quote_draft(
            "QUOTE-RAW", "LEAD-RAW", "AO-PILOT", "ZAR", 560000.0, 12
        )
        raw_subject = raw_plane.quote_authority_subject("QUOTE-RAW")
        raw_receipt = owner_receipt(
            gate=raw_subject["gate"],
            evidence_id=raw_subject["evidence_id"],
            content_sha256=raw_subject["content_sha256"],
            now=now,
        )
        raw_plane.owner_receipts[raw_receipt.receipt_id] = raw_receipt
        raw_plane.owner_validator.receipts[raw_receipt.receipt_id] = raw_receipt
        try:
            raw_plane.approve_quote(
                "QUOTE-RAW",
                owner_decision_receipt_id=raw_receipt.receipt_id,
                now=now_text,
            )
        except PermissionError as exc:
            checks["raw_authority_rejected"] = "AUTHORITY_SNAPSHOT_REQUIRED" in str(exc)
        else:
            checks["raw_authority_rejected"] = False

        plane = AuthoritySnapshotCommercialControlPlane(
            root / "governed",
            authority_snapshot=snapshot,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        plane.create_lead("LEAD-1", "org", "inbound", "manual delay")
        plane.create_quote_draft(
            "QUOTE-1", "LEAD-1", "AO-PILOT", "ZAR", 560000.0, 12
        )
        subject = plane.quote_authority_subject("QUOTE-1")
        receipt = owner_receipt(
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
            now=now,
        )
        governed = AuthoritySnapshotCommercialControlPlane(
            root / "governed",
            authority_snapshot=snapshot,
            owner_receipts={receipt.receipt_id: receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        quote = governed.approve_quote(
            "QUOTE-1",
            owner_decision_receipt_id=receipt.receipt_id,
            now=now_text,
        )
        readback = governed.governed_authority_readback()
        checks["governed_quote_presentation_verified"] = (
            quote["status"] == "OWNER_APPROVED_FOR_EXTERNAL_PRESENTATION"
            and quote["external_send_performed"] is False
            and quote["financial_commitment"] is False
        )
        checks["snapshot_readback_verified"] = (
            readback["authority_snapshot"]["snapshot_present"] is True
            and readback["authority_snapshot"]["domains"]["owner_decision"]["valid"] is True
            and readback["authority_snapshot"]["raw_authority_input_grants_live_authority"] is False
        )
        checks["zero_revenue_preserved"] = (
            readback["revenue"]["live_verified_revenue_events"] == 0
        )
        checks["governance_ledger_integrity"] = readback["authority_ledger_integrity"] is True
        checks["external_evidence_ledger_integrity"] = (
            readback["external_evidence_ledger_integrity"] is True
        )

    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("authority snapshot proof failed: " + ",".join(failed))

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "control_id": "AO-COMMERCIAL-AUTHORITY-SNAPSHOT-V3",
        "status": "AUTHORITY_SNAPSHOT_CONTROL_PROVIDER_PROOF_VERIFIED",
        "scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": checks,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_sha256": snapshot.snapshot_sha256,
        "source_projection_sha256": snapshot.source_projection_sha256,
        "source_ledger_head": snapshot.source_ledger_head,
        "verified_live_revenue_events": 0,
        "external_gate_effect": "UNCHANGED",
        "cloud_run_operation_proven": False,
        "payment_provider_operation_proven": False,
        "full_commercial_maturity": False,
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
        "truth_boundary": (
            "The proof validates the authority-snapshot control contract with synthetic "
            "provider-conformance data. It does not establish customer demand, a signed "
            "contract, payment, revenue, Cloud Run operation, enterprise assurance, "
            "partner adoption, an external case study or production scale."
        ),
    }
    receipt["receipt_sha256"] = digest(receipt)
    output = Path("artifacts")
    output.mkdir(parents=True, exist_ok=True)
    (output / "authority-snapshot-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
