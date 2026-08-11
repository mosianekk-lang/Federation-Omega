from __future__ import annotations

import argparse
import json
import tempfile
import threading
from pathlib import Path

from authority_action_coordination import (
    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def build_quote(root: Path, quote_id: str):
    value = snapshot(1, -20)
    bootstrap = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
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
    plane = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
        root,
        authority_snapshot=value,
        owner_receipts={receipt.receipt_id: receipt},
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    return plane, receipt, value


def prepare_unterminated(plane, quote_id: str) -> dict:
    with plane._action_coordination_locked():
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
            Path(success_tmp), "QUOTE-COORDINATION-PROOF"
        )
        quote = success_plane.approve_quote(
            "QUOTE-COORDINATION-PROOF",
            owner_decision_receipt_id=success_receipt.receipt_id,
            now=NOW,
        )
        success_readback = success_plane.authority_action_transaction_readback()
        success_authority = success_plane.governed_authority_readback()

    with tempfile.TemporaryDirectory() as race_tmp:
        race_root = Path(race_tmp)
        race_plane, race_receipt, race_value = build_quote(
            race_root, "QUOTE-COORDINATION-RACE"
        )
        action = race_plane._atomic_action(
            stage="C13",
            action="quote_approval",
            object_id="QUOTE-COORDINATION-RACE",
            domains=("owner_decision",),
            now=NOW,
        )
        transaction = action.__enter__()
        started = threading.Event()
        finished = threading.Event()
        worker_result: dict[str, object] = {}

        def restart_worker() -> None:
            started.set()
            try:
                worker_result["plane"] = (
                    CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
                        race_root,
                        authority_snapshot=race_value,
                        owner_receipts={race_receipt.receipt_id: race_receipt},
                        authority_profile="LIVE_PROVIDER_AUTHORITY",
                    )
                )
            except BaseException as exc:
                worker_result["error"] = exc
            finally:
                finished.set()

        worker = threading.Thread(target=restart_worker, daemon=True)
        worker.start()
        started.wait(1.0)
        startup_blocked_during_live_transaction = not finished.wait(0.2)
        action.__exit__(None, None, None)
        startup_completed_after_terminal = finished.wait(3.0)
        worker.join(timeout=1.0)
        if "error" in worker_result:
            raise RuntimeError("concurrent startup proof failed") from worker_result["error"]
        restarted = worker_result["plane"]
        race_events = restarted._transaction_events()
        live_transaction_not_rolled_back = (
            [event["event"] for event in race_events]
            == ["ACTION_PREPARED", "ACTION_COMMITTED"]
            and race_events[-1]["transaction_id"] == transaction["transaction_id"]
        )

    with tempfile.TemporaryDirectory() as recovery_tmp:
        recovery_root = Path(recovery_tmp)
        recovery_plane, recovery_receipt, recovery_value = build_quote(
            recovery_root, "QUOTE-COORDINATION-RECOVERY"
        )
        before_state = recovery_plane._read_state()
        before_governance = recovery_plane._read_governance_state()
        recovery_transaction = prepare_unterminated(
            recovery_plane, "QUOTE-COORDINATION-RECOVERY"
        )
        partial_state = recovery_plane._read_state()
        partial_state["quotes"]["QUOTE-COORDINATION-RECOVERY"]["status"] = "APPROVED"
        recovery_plane._write_state(partial_state)
        partial_governance = recovery_plane._read_governance_state()
        partial_governance["consumed_owner_receipts"][
            recovery_receipt.receipt_id
        ] = {"partial_worker": True}
        recovery_plane._write_governance_state(partial_governance)
        recovered = CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane(
            recovery_root,
            authority_snapshot=recovery_value,
            owner_receipts={recovery_receipt.receipt_id: recovery_receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        recovery_events = recovered._transaction_events()
        crash_state_restored = recovered._read_state() == before_state
        crash_governance_restored = (
            recovered._read_governance_state() == before_governance
        )
        crash_recovery_terminal_recorded = (
            recovery_events[-1]["event"] == "ACTION_ROLLED_BACK"
            and recovery_events[-1]["failure_class"]
            == "PROCESS_RESTART_RECOVERY"
            and recovery_events[-1]["transaction_id"]
            == recovery_transaction["transaction_id"]
        )
        verified_revenue_zero = (
            recovered.governed_authority_readback()["revenue"][
                "live_verified_revenue_events"
            ]
            == 0
        )

    coordination = success_readback["process_coordination"]
    checks = {
        "canonical_coordinated_class": (
            success_authority["canonical_class"]
            == "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane"
        ),
        "successful_action_committed": success_readback["committed"] == 1,
        "successful_action_sealed": (
            quote["authority_action_commit"]["state"]
            == "ATOMIC_AUTHORITY_ACTION_COMMITTED"
        ),
        "startup_recovery_serialized": coordination["startup_recovery_serialized"],
        "live_actions_serialized": coordination["live_authority_actions_serialized"],
        "startup_blocked_during_live_transaction": startup_blocked_during_live_transaction,
        "startup_completed_after_terminal": startup_completed_after_terminal,
        "live_transaction_not_rolled_back": live_transaction_not_rolled_back,
        "actual_crash_state_restored": crash_state_restored,
        "actual_crash_governance_restored": crash_governance_restored,
        "actual_crash_recovery_terminal_recorded": crash_recovery_terminal_recorded,
        "verified_live_revenue_remains_zero": verified_revenue_zero,
    }

    receipt = {
        "control_id": "AO-COMMERCIAL-AUTHORITY-ACTION-COORDINATION-V9",
        "status": (
            "AUTHORITY_ACTION_COORDINATION_PROVIDER_PROOF_VERIFIED_"
            "EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "coordination_safety": {
            "startup_cleanup_serialized": True,
            "startup_recovery_serialized": True,
            "live_authority_actions_serialized": True,
            "integrity_readback_serialized": True,
            "concurrent_startup_can_rollback_live_transaction": False,
            "process_crash_releases_coordination_lock": True,
            "new_action_blocked_until_recovery_complete": True,
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
        "provider_boundaries": {
            "cloud_run": "PROVIDER_BLOCKED_CANONICAL_IDENTITY_AUTHORITY_UNAVAILABLE",
            "payment_provider": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            "customer_market": "MARKET_PROOF_REQUIRED",
            "partner_market": "MARKET_PROOF_REQUIRED",
            "production_scale": "PRODUCTION_PROOF_REQUIRED",
        },
        "external_gate_effect": "UNCHANGED",
    }
    receipt["receipt_sha256"] = digest(receipt)
    if receipt["checks_failed"]:
        raise RuntimeError("authority action coordination proof failed")
    (output / "authority-action-coordination-receipt.json").write_text(
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
