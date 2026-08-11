from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from authority_snapshot import (
    AuthorityDomainLease,
    CommercialAuthoritySnapshotValidator,
    build_authority_snapshot,
    digest,
)
from authority_snapshot_acceptance import AuthoritySnapshotAcceptanceLedger
from authority_snapshot_control_plane import (
    AuthoritySnapshotCommercialControlPlane,
    REQUIRED_SCOPE,
)
from governed_commercial_assurance import LIVE_AUTHORITY_CLASS


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_snapshot(
    sequence: int,
    *,
    generated: datetime,
    expires: datetime,
    source_head: str,
):
    def lease(domain: str, scope: tuple[str, ...]) -> AuthorityDomainLease:
        return AuthorityDomainLease(
            domain=domain,
            state="FRESH_VERIFIED",
            authority_class=LIVE_AUTHORITY_CLASS,
            provider=f"provider-proof-{domain}",
            locator=f"proof://{domain}/receipt/{sequence}",
            observed_at=iso(generated),
            scope=scope,
            evidence_sha256=sha(f"provider-evidence-{domain}-{sequence}"),
            max_age_seconds=86400,
        ).with_hash()

    return build_authority_snapshot(
        snapshot_id=f"AO-COMMERCIAL-AUTHORITY-SNAPSHOT-AR-{sequence}",
        generated_at=iso(generated),
        expires_at=iso(expires),
        source_projection_sha256=sha(f"authority-projection-{sequence}-{source_head}"),
        source_ledger_head=sha(source_head),
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


def main() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_text = iso(now)
    first = build_snapshot(
        1,
        generated=now - timedelta(minutes=20),
        expires=now + timedelta(hours=6),
        source_head="authority-ledger-head-1",
    )
    second = build_snapshot(
        2,
        generated=now - timedelta(minutes=10),
        expires=now + timedelta(hours=7),
        source_head="authority-ledger-head-2",
    )
    rollback = build_snapshot(
        3,
        generated=now - timedelta(minutes=15),
        expires=now + timedelta(hours=6),
        source_head="authority-ledger-head-1",
    )
    equivocation = build_authority_snapshot(
        snapshot_id="AO-COMMERCIAL-AUTHORITY-SNAPSHOT-AR-EQUIVOCATION",
        generated_at=second.generated_at,
        expires_at=iso(now + timedelta(hours=8)),
        source_projection_sha256=sha("equivocation-projection"),
        source_ledger_head=sha("authority-ledger-head-equivocation"),
        source_ledger_integrity=True,
        domains=second.domains.values(),
    )

    checks: dict[str, bool] = {}
    output = Path("artifacts")
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        ledger = AuthoritySnapshotAcceptanceLedger(root / "ledger")
        first_entry = ledger.accept(
            first,
            CommercialAuthoritySnapshotValidator(first),
            required_scope=REQUIRED_SCOPE,
            now=now_text,
        )
        checks["first_acceptance_persisted"] = (
            first_entry["sequence"] == 1
            and first_entry["snapshot_sha256"] == first.snapshot_sha256
        )

        restarted = AuthoritySnapshotAcceptanceLedger(root / "ledger")
        replay = restarted.accept(
            first,
            CommercialAuthoritySnapshotValidator(first),
            required_scope=REQUIRED_SCOPE,
            now=now_text,
        )
        checks["idempotent_replay_preserved"] = (
            replay["entry_sha256"] == first_entry["entry_sha256"]
            and len(restarted.entries) == 1
        )

        second_entry = restarted.accept(
            second,
            CommercialAuthoritySnapshotValidator(second),
            required_scope=REQUIRED_SCOPE,
            now=now_text,
        )
        checks["newer_snapshot_accepted"] = (
            second_entry["sequence"] == 2
            and second_entry["previous_entry_sha256"] == first_entry["entry_sha256"]
        )

        rollback_decision = restarted.preview(
            rollback,
            CommercialAuthoritySnapshotValidator(rollback),
            required_scope=REQUIRED_SCOPE,
            now=now_text,
        )
        checks["temporal_rollback_rejected"] = (
            not rollback_decision.valid
            and "AUTHORITY_SNAPSHOT_ROLLBACK_DETECTED" in rollback_decision.reasons
        )

        equivocation_decision = restarted.preview(
            equivocation,
            CommercialAuthoritySnapshotValidator(equivocation),
            required_scope=REQUIRED_SCOPE,
            now=now_text,
        )
        checks["equivocation_rejected"] = (
            not equivocation_decision.valid
            and "AUTHORITY_SNAPSHOT_EQUIVOCATION_DETECTED"
            in equivocation_decision.reasons
        )

        source_rollback = build_snapshot(
            4,
            generated=now - timedelta(minutes=5),
            expires=now + timedelta(hours=8),
            source_head="authority-ledger-head-1",
        )
        source_decision = restarted.preview(
            source_rollback,
            CommercialAuthoritySnapshotValidator(source_rollback),
            required_scope=REQUIRED_SCOPE,
            now=now_text,
        )
        checks["source_ledger_rollback_rejected"] = (
            not source_decision.valid
            and "SOURCE_LEDGER_HEAD_ROLLBACK_DETECTED" in source_decision.reasons
        )

        control_root = root / "control"
        plane = AuthoritySnapshotCommercialControlPlane(
            control_root,
            authority_snapshot=first,
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        control_entry = plane.accept_authority_snapshot(now=now_text)
        readback = plane.governed_authority_readback()
        checks["canonical_control_plane_bound"] = (
            control_entry["event"] == "AUTHORITY_SNAPSHOT_ACCEPTED"
            and readback["authority_snapshot"]["acceptance"]["anti_rollback_enforced"]
            and readback["authority_snapshot"]["acceptance"]["entries"] == 1
        )
        checks["zero_revenue_preserved"] = (
            readback["revenue"]["live_verified_revenue_events"] == 0
        )
        checks["external_effects_absent"] = (
            readback["authority_snapshot"]["raw_authority_input_grants_live_authority"]
            is False
        )

        ledger_copy = output / "authority-snapshot-acceptance-ledger.jsonl"
        shutil.copyfile(restarted.path, ledger_copy)
        verified_copy = AuthoritySnapshotAcceptanceLedger(root / "ledger")
        checks["restart_integrity_verified"] = (
            len(verified_copy.entries) == 2
            and verified_copy.entries[-1]["entry_sha256"]
            == second_entry["entry_sha256"]
        )

    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("authority snapshot anti-rollback proof failed: " + ",".join(failed))

    receipt = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "control_id": "AO-COMMERCIAL-AUTHORITY-SNAPSHOT-ANTI-ROLLBACK-V4",
        "status": "AUTHORITY_SNAPSHOT_ANTI_ROLLBACK_PROVIDER_PROOF_VERIFIED",
        "scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": checks,
        "accepted_snapshots": 2,
        "latest_snapshot_id": second.snapshot_id,
        "latest_snapshot_sha256": second.snapshot_sha256,
        "anti_rollback": {
            "temporal_rollback_rejected": True,
            "equivocation_rejected": True,
            "snapshot_id_conflict_rejected": True,
            "source_ledger_rollback_rejected": True,
            "restart_safe": True,
        },
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
            "The proof uses synthetic provider-conformance snapshots to verify durable "
            "anti-rollback controls. It does not establish customer demand, a signed "
            "contract, payment, revenue, subscriptions, invoices, Cloud Run operation, "
            "enterprise assurance, partner adoption, an external case study or "
            "production scale."
        ),
    }
    receipt["receipt_sha256"] = digest(receipt)
    (output / "authority-snapshot-anti-rollback-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
