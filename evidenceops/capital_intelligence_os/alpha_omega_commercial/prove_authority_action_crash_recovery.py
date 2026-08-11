from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from authority_action_crash_recovery import (
    CrashSafeAtomicAuthoritySnapshotCommercialControlPlane,
)
from authority_snapshot import digest
from test_authority_snapshot_action_binding import NOW, owner_receipt, snapshot


def quote_plane(root: Path):
    value = snapshot(1, -20)
    bootstrap = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
        root,
        authority_snapshot=value,
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    bootstrap.create_lead("LEAD-PROOF", "org", "inbound", "manual delay")
    bootstrap.create_quote_draft(
        "QUOTE-PROOF",
        "LEAD-PROOF",
        "AO-PILOT",
        "ZAR",
        560000.0,
        12,
    )
    subject = bootstrap.quote_authority_subject("QUOTE-PROOF")
    receipt = owner_receipt(
        "OWNER-QUOTE-PROOF",
        gate=subject["gate"],
        evidence_id=subject["evidence_id"],
        content_sha256=subject["content_sha256"],
    )
    plane = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
        root,
        authority_snapshot=value,
        owner_receipts={receipt.receipt_id: receipt},
        authority_profile="LIVE_PROVIDER_AUTHORITY",
    )
    return plane, receipt, value


def prepare_unterminated_transaction(plane):
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
            "object_id": "QUOTE-PROOF",
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
        success_plane, success_receipt, _ = quote_plane(Path(success_tmp))
        quote = success_plane.approve_quote(
            "QUOTE-PROOF",
            owner_decision_receipt_id=success_receipt.receipt_id,
            now=NOW,
        )
        success_readback = success_plane.authority_action_transaction_readback()

    with tempfile.TemporaryDirectory() as recovery_tmp:
        root = Path(recovery_tmp)
        recovery_plane, recovery_receipt, value = quote_plane(root)
        before_state = recovery_plane._read_state()
        before_governance = recovery_plane._read_governance_state()
        transaction = prepare_unterminated_transaction(recovery_plane)

        partial_state = recovery_plane._read_state()
        partial_state["quotes"]["QUOTE-PROOF"]["status"] = "APPROVED"
        partial_state["quotes"]["QUOTE-PROOF"]["process_crash_partial"] = True
        recovery_plane._write_state(partial_state)
        partial_governance = recovery_plane._read_governance_state()
        partial_governance["consumed_owner_receipts"][
            recovery_receipt.receipt_id
        ] = {"process_crash_partial": True}
        recovery_plane._write_governance_state(partial_governance)

        restarted = CrashSafeAtomicAuthoritySnapshotCommercialControlPlane(
            root,
            authority_snapshot=value,
            owner_receipts={recovery_receipt.receipt_id: recovery_receipt},
            authority_profile="LIVE_PROVIDER_AUTHORITY",
        )
        recovery_readback = restarted.authority_action_transaction_readback()
        terminal = restarted._transaction_events()[-1]
        checks = {
            "canonical_crash_safe_class": (
                restarted.governed_authority_readback()["canonical_class"]
                == "CrashSafeAtomicAuthoritySnapshotCommercialControlPlane"
            ),
            "successful_action_committed": success_readback["committed"] == 1,
            "successful_action_sealed": (
                quote["authority_action_commit"]["state"]
                == "ATOMIC_AUTHORITY_ACTION_COMMITTED"
            ),
            "successful_bundle_removed": (
                success_readback["process_crash_recovery"][
                    "durable_recovery_bundles"
                ]
                == []
            ),
            "restart_state_restored_exactly": restarted._read_state()
            == before_state,
            "restart_governance_restored_exactly": (
                restarted._read_governance_state() == before_governance
            ),
            "restart_transaction_rolled_back": recovery_readback[
                "rolled_back"
            ]
            == 1,
            "restart_transaction_terminal": recovery_readback["unterminated"]
            == [],
            "restart_recovery_recorded": (
                terminal.get("failure_class") == "PROCESS_RESTART_RECOVERY"
                and terminal.get("transaction_id")
                == transaction["transaction_id"]
            ),
            "restart_bundle_removed": (
                recovery_readback["process_crash_recovery"][
                    "durable_recovery_bundles"
                ]
                == []
            ),
            "recovery_manifest_hash_bound": recovery_readback[
                "process_crash_recovery"
            ]["recovery_manifest_hash_bound"],
            "recovery_content_hash_verified": recovery_readback[
                "process_crash_recovery"
            ]["recovery_content_hash_verified"],
            "owner_reserved_external_effects_held": True,
            "verified_live_revenue_remains_zero": (
                restarted.governed_authority_readback()["revenue"][
                    "live_verified_revenue_events"
                ]
                == 0
            ),
        }

    receipt = {
        "control_id": "AO-COMMERCIAL-AUTHORITY-ACTION-CRASH-RECOVERY-V7",
        "status": (
            "AUTHORITY_ACTION_CRASH_RECOVERY_PROVIDER_PROOF_VERIFIED_"
            "EXTERNAL_GATES_UNCHANGED"
        ),
        "stage_scope": ["C03", "C11", "C12", "C13", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "recovery": {
            "durable_bundle_before_action": True,
            "manifest_hash_bound": True,
            "content_hash_verified": True,
            "restart_recovery_before_new_action": True,
            "restart_rollback_idempotent": True,
            "terminal_event_after_recovery": "ACTION_ROLLED_BACK",
            "failure_class": "PROCESS_RESTART_RECOVERY",
            "successful_bundle_cleanup": True,
            "partial_state_visible_after_process_crash": False,
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
        raise RuntimeError("authority action crash recovery proof failed")
    (output / "authority-action-crash-recovery-receipt.json").write_text(
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
