from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from authority_action_crash_recovery import (
    CrashSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_action_journal import (
    JournalSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def build_quote(root: Path, plane_class, quote_id: str):
    value = snapshot(1, -20)
    bootstrap = plane_class(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    lead_id = quote_id.replace("QUOTE", "LEAD")
    bootstrap.create_lead(lead_id, "org", "inbound", "manual delay")
    bootstrap.create_quote_draft(
        quote_id,
        lead_id,
        "AO-PILOT",
        "ZAR",
        560000.0,
        12,
    )
    subject = bootstrap.quote_authority_subject(quote_id)
    receipt = owner_receipt(
        "OWNER-" + quote_id,
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = plane_class(
        root,
        authority_snapshot=value,
        owner_receipts={receipt.receipt_id: receipt},
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    return plane, receipt, value


def prepare_unterminated(plane, quote_id: str) -> dict:
    plane.accept_authority_snapshot(now=NOW)
    ledger = plane.authority_snapshot_acceptance
    with ledger._locked():
        entry = plane._latest_locked_acceptance(now=NOW)
        current = plane.authority_snapshot_validator.snapshot
        assert current is not None
        events = plane._transaction_events()
        transaction = {
            "transaction_id": f"AO-ACTION-{len(events) + 1:08d}",
            "stage": "C13",
            "action": "quote_approval",
            "object_id": quote_id,
            "snapshot_id": current.snapshot_id,
            "snapshot_sha256": current.snapshot_sha256,
            "acceptance_sequence": entry["sequence"],
            "acceptance_entry_sha256": entry["entry_sha256"],
            "domains": ["owner_decision"],
            "recorded_at": NOW,
        }
        backup = plane._capture_transaction_files()
        plane._prepare_recovery_bundle(transaction, backup)
        plane._append_transaction_event("ACTION_PREPARED", transaction)
    return transaction


def prove(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as success_tmp:
        success_plane, success_receipt, _ = build_quote(
            Path(success_tmp),
            JournalSafeAtomicAuthoritySnapshotCommercialControlPlane,
            "QUOTE-JOURNAL-PROOF",
        )
        quote = success_plane.approve_quote(
            "QUOTE-JOURNAL-PROOF",
            owner_decision_receipt_id=success_receipt.receipt_id,
            now=NOW,
        )
        success_readback = success_plane.authority_action_transaction_readback()

    with tempfile.TemporaryDirectory() as recovery_tmp:
        recovery_root = Path(recovery_tmp)
        recovery_plane, recovery_receipt, value = build_quote(
            recovery_root,
            JournalSafeAtomicAuthoritySnapshotCommercialControlPlane,
            "QUOTE-JOURNAL-RECOVERY",
        )
        before_state = recovery_plane._read_state()
        before_governance = recovery_plane._read_governance_state()
        transaction = prepare_unterminated(
            recovery_plane, "QUOTE-JOURNAL-RECOVERY"
        )
        partial_state = recovery_plane._read_state()
        partial_state["quotes"]["QUOTE-JOURNAL-RECOVERY"]["status"] = "APPROVED"
        partial_state["quotes"]["QUOTE-JOURNAL-RECOVERY"][
            "torn_terminal_publication"
        ] = True
        recovery_plane._write_state(partial_state)
        partial_governance = recovery_plane._read_governance_state()
        partial_governance["consumed_owner_receipts"][
            recovery_receipt.receipt_id
        ] = {"torn_terminal_publication": True}
        recovery_plane._write_governance_state(partial_governance)
        temporary = (
            recovery_plane.transaction_journal_root / ".terminal.event.tmp"
        )
        temporary.write_text('{"event":"ACTION_COMMITTED"', encoding="utf-8")

        restarted = JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
            recovery_root,
            authority_snapshot=value,
            owner_receipts={recovery_receipt.receipt_id: recovery_receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        recovery_readback = restarted.authority_action_transaction_readback()
        recovery_events = restarted._transaction_events()

    with tempfile.TemporaryDirectory() as legacy_tmp:
        legacy_root = Path(legacy_tmp)
        legacy_plane, legacy_receipt, legacy_value = build_quote(
            legacy_root,
            CrashSafeAtomicAuthoritySnapshotCommercialControlPlane,
            "QUOTE-LEGACY-PROOF",
        )
        legacy_plane.approve_quote(
            "QUOTE-LEGACY-PROOF",
            owner_decision_receipt_id=legacy_receipt.receipt_id,
            now=NOW,
        )
        legacy_plane.create_lead(
            "LEAD-JOURNAL-NEXT", "org", "inbound", "manual delay"
        )
        legacy_plane.create_quote_draft(
            "QUOTE-JOURNAL-NEXT",
            "LEAD-JOURNAL-NEXT",
            "AO-PILOT",
            "ZAR",
            560000.0,
            12,
        )
        subject = legacy_plane.quote_authority_subject("QUOTE-JOURNAL-NEXT")
        next_receipt = owner_receipt(
            "OWNER-QUOTE-JOURNAL-NEXT",
            gate=subject["gate"],
            evidence_id=subject["evidence_id"],
            content_sha256=subject["content_sha256"],
        )
        journal_plane = JournalSafeAtomicAuthoritySnapshotCommercialControlPlane(
            legacy_root,
            authority_snapshot=legacy_value,
            owner_receipts={next_receipt.receipt_id: next_receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        journal_plane.approve_quote(
            "QUOTE-JOURNAL-NEXT",
            owner_decision_receipt_id=next_receipt.receipt_id,
            now=NOW,
        )
        legacy_readback = journal_plane.authority_action_journal_readback()
        legacy_events = journal_plane._transaction_events()

    journal = success_readback["transaction_journal"]
    checks = {
        "canonical_journal_safe_class": (
            success_plane.governed_authority_readback()["canonical_class"]
            == "JournalSafeAtomicAuthoritySnapshotCommercialControlPlane"
        ),
        "successful_action_committed": success_readback["committed"] == 1,
        "successful_action_sealed": (
            quote["authority_action_commit"]["state"]
            == "ATOMIC_AUTHORITY_ACTION_COMMITTED"
        ),
        "successful_events_atomically_published": (
            journal["atomically_published_events"] == 2
        ),
        "successful_journal_has_no_incomplete_publication": (
            journal["incomplete_publications"] == []
        ),
        "event_filename_and_content_hash_bound": (
            journal["event_filename_hash_bound"]
            and journal["event_file_hash_bound"]
        ),
        "restart_state_restored_exactly": restarted._read_state() == before_state,
        "restart_governance_restored_exactly": (
            restarted._read_governance_state() == before_governance
        ),
        "torn_terminal_publication_removed": (
            not temporary.exists()
            and recovery_readback["transaction_journal"][
                "incomplete_publications"
            ]
            == []
        ),
        "restart_recovery_terminal_recorded": (
            recovery_events[-1].get("failure_class")
            == "PROCESS_RESTART_RECOVERY"
            and recovery_events[-1].get("transaction_id")
            == transaction["transaction_id"]
        ),
        "legacy_prefix_and_new_journal_chain_verified": (
            legacy_readback["legacy_jsonl_events"] == 2
            and legacy_readback["atomically_published_events"] == 2
            and [event["sequence"] for event in legacy_events] == [1, 2, 3, 4]
            and legacy_events[2]["previous_event_sha256"]
            == legacy_events[1]["event_sha256"]
        ),
        "verified_live_revenue_remains_zero": (
            restarted.governed_authority_readback()["revenue"][
                "live_verified_revenue_events"
            ]
            == 0
        ),
    }

    receipt = {
        "control_id": "AO-COMMERCIAL-AUTHORITY-ACTION-JOURNAL-V8",
        "status": (
            "AUTHORITY_ACTION_JOURNAL_PROVIDER_PROOF_VERIFIED_"
            "EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "journal_safety": {
            "legacy_jsonl_prefix_frozen": True,
            "new_event_atomic_publication": True,
            "event_file_fsync": True,
            "journal_directory_fsync": True,
            "event_filename_hash_bound": True,
            "event_content_hash_bound": True,
            "incomplete_publication_removed_before_recovery": True,
            "prepared_without_terminal_rolls_back_after_restart": True,
            "torn_transaction_event_visible_after_process_crash": False,
        },
        "commercial_truth": {
            "service_enabled_platform_prioritised": True,
            "self_service_saas_held": True,
            "verified_live_revenue_events": 0,
            "customer_demand_proven": False,
            "signed_customer_contract_proven": False,
            "payment_provider_operation_proven": False,
            "cloud_run_operation_proven": False,
            "enterprise_attestation_proven": False,
            "partner_adoption_proven": False,
            "external_customer_case_study_proven": False,
            "production_scale_proven": False,
            "full_commercial_maturity": False,
        },
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        },
        "external_gate_effect": "UNCHANGED",
    }
    receipt["receipt_sha256"] = digest(receipt)
    if receipt["checks_failed"]:
        raise RuntimeError("authority action journal proof failed")
    (output / "authority-action-journal-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    receipt = prove(args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
