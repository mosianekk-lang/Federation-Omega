from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from authority_snapshot import digest


ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def run(output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    release = load("authority_action_crash_recovery_release_receipt.json")
    checkpoint = load("authority_action_crash_recovery_release_checkpoint.json")
    contract = load("authority_action_crash_recovery_contract.json")
    implementation_checkpoint = load("authority_action_crash_recovery_checkpoint.json")
    api = load("canonical_commercial_api.json")
    programme = load("programme.json")
    institution = json.loads(
        (ROOT.parent / "alpha_omega_v30" / "maturity.json").read_text(
            encoding="utf-8"
        )
    )

    receipt_payload = dict(release)
    recorded_receipt_sha = receipt_payload.pop("receipt_sha256")
    workflows = release["final_head_workflows"]
    checks = {
        "release_receipt_integrity": digest(receipt_payload) == recorded_receipt_sha,
        "implementation_pr_and_merge_bound": (
            release["dependency"]["implementation_pull_request"] == 128
            and release["dependency"]["implementation_merge_commit"]
            == "ac6314279de32ffbc220e75c8c01c9b636e9c83c"
        ),
        "dependency_order_preserved": release["stage_scope"]
        == ["C03", "C11", "C12", "C13", "C15"],
        "final_provider_artifact_bound": (
            release["final_head_provider_proof"]["head_sha"]
            == "0efe5ecdb1f995998aa7d11355f0ea128fd92b60"
            and release["final_head_provider_proof"]["workflow_run"]
            == 30884518082
            and release["final_head_provider_proof"]["artifact_id"]
            == 8882538570
            and release["final_head_provider_proof"]["artifact_digest"]
            == "sha256:1fe56ab8b12f88b691230748b3b9a550b321423a734ca2a210b11f5cb797baae"
            and release["final_head_provider_proof"]["receipt_sha256"]
            == "2aba04e0c8b885e818df78d98b39088f488d7d05be2193b163727232192df748"
            and release["final_head_provider_proof"]["checks_required"] == 14
            and release["final_head_provider_proof"]["checks_failed"] == 0
        ),
        "all_final_workflows_recorded": len(workflows) == 17
        and all(isinstance(run_id, int) and run_id > 0 for run_id in workflows.values()),
        "required_regression_workflows_bound": (
            workflows["C01_C05"] == 30884517991
            and workflows["C06_C09"] == 30884517993
            and workflows["C10_C15"] == 30884517999
            and workflows["authority_action_atomicity"] == 30884518094
            and workflows["repository_leak_guard"] == 30884517980
            and workflows["superior_logic_ci"] == 30884518041
        ),
        "drive_release_exactly_bound": (
            release["google_drive_release"]["file_id"]
            == "18jpciwkXdRXwqAH-9OWn30wSVjFnaRIPe05GHCqZ-rA"
            and release["google_drive_release"]["revision_id"]
            == "AIroW36fIabzWJPC2E4DtjvDrWeAsAM4L1E4hqhQEn770J2Td7ctDwBvy2D6h186YSt2lXnoezftcIiHC1EvUnTrIlt-EnUqlMwXN2c0PLQ"
            and release["google_drive_release"]["readback_sha256"]
            == "0a937afcbf4ab1c385296b6b99c53541bb3c814e17f6b009278da566e876bd12"
            and release["google_drive_release"]["readback_length"] == 4057
            and release["google_drive_release"]["readback_verified"] is True
            and release["google_drive_release"]["shared"] is False
        ),
        "checkpoint_matches_release": (
            checkpoint["implementation_release"]["pull_request"] == 128
            and checkpoint["implementation_release"]["merge_commit"]
            == release["dependency"]["implementation_merge_commit"]
            and checkpoint["implementation_release"]["release_receipt_sha256"]
            == recorded_receipt_sha
            and checkpoint["provider_proof"]["artifact_id"]
            == release["final_head_provider_proof"]["artifact_id"]
            and checkpoint["google_drive_release"]["file_id"]
            == release["google_drive_release"]["file_id"]
            and checkpoint["google_drive_release"]["readback_sha256"]
            == release["google_drive_release"]["readback_sha256"]
        ),
        "implementation_contract_bound": (
            contract["control_id"]
            == "AO-COMMERCIAL-AUTHORITY-ACTION-CRASH-RECOVERY-V7"
            and contract["dependency"]["preceding_pull_request"] == 127
            and contract["crash_recovery_rules"]["durable_bundle_before_action"]
            is True
            and contract["crash_recovery_rules"]["restart_recovery_before_new_action"]
            is True
            and contract["crash_recovery_rules"]["partial_state_visible_after_process_crash"]
            is False
        ),
        "implementation_checkpoint_preserves_boundaries": (
            implementation_checkpoint["dependency_checkpoint"]["preceding_pull_request"]
            == 127
            and all(
                value is False
                for value in implementation_checkpoint["external_gates"].values()
            )
            and implementation_checkpoint["commercial_truth"][
                "verified_live_revenue_events"
            ]
            == 0
        ),
        "canonical_api_revision_bound": (
            api["api_id"] == "AO-COMMERCIAL-CANONICAL-API-V3"
            and api["current_capability_revision"]
            == "AO-COMMERCIAL-AUTHORITY-ACTION-CRASH-RECOVERY-V7"
            and api["current_canonical_class"]
            == "CrashSafeAtomicAuthoritySnapshotCommercialControlPlane"
            and api["authority_use"]["durable_recovery_bundle_required"] is True
            and api["authority_use"]["restart_recovery_before_new_action"] is True
            and api["authority_use"]["process_crash_partial_state_visible"]
            is False
        ),
        "service_first_strategy_preserved": (
            release["strategy"]
            == "SERVICE_ENABLED_PLATFORM_BEFORE_SELF_SERVICE_SAAS"
            and release["self_service_saas"] == "HELD"
            and api["service_first_strategy"]
            == "SERVICE_ENABLED_PLATFORM_BEFORE_SELF_SERVICE_SAAS"
        ),
        "external_gates_remain_false": all(
            value is False for value in release["external_gates"].values()
        )
        and not programme["external_gate_evidence"],
        "zero_revenue_preserved": (
            release["commercial_truth"]["verified_live_revenue_events"] == 0
            and checkpoint["commercial_truth"]["verified_live_revenue_events"]
            == 0
            and api["verified_live_revenue_events"] == 0
        ),
        "no_cloud_payment_or_distributed_atomicity_claim": (
            release["commercial_truth"]["cloud_run_operation_proven"] is False
            and release["commercial_truth"]["payment_provider_operation_proven"]
            is False
            and release["effective_controls"]["distributed_provider_atomicity_proven"]
            is False
        ),
        "owner_authority_preserved": all(
            value.startswith("OWNER_RESERVED")
            for value in release["owner_authority"].values()
        ),
        "institution_external_completion_still_blocked": (
            institution["phases"][-1]["id"] == "P15"
            and "BLOCKED" in institution["phases"][-1]["status"]
        ),
        "full_commercial_maturity_not_claimed": (
            release["commercial_truth"]["full_commercial_maturity"] is False
            and api["full_commercial_maturity"] is False
        ),
    }

    proof: dict[str, Any] = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_id": "AO-COMMERCIAL-AUTHORITY-ACTION-CRASH-RECOVERY-V7-RELEASE-PROOF",
        "status": (
            "AUTHORITY_ACTION_CRASH_RECOVERY_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED"
            if all(checks.values())
            else "AUTHORITY_ACTION_CRASH_RECOVERY_RELEASE_RECONCILIATION_FAILED"
        ),
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not value for value in checks.values()),
        "release_receipt_sha256": recorded_receipt_sha,
        "implementation_merge_commit": release["dependency"][
            "implementation_merge_commit"
        ],
        "provider_artifact_id": release["final_head_provider_proof"]["artifact_id"],
        "provider_artifact_digest": release["final_head_provider_proof"][
            "artifact_digest"
        ],
        "google_drive_file_id": release["google_drive_release"]["file_id"],
        "google_drive_revision_id": release["google_drive_release"]["revision_id"],
        "google_drive_readback_sha256": release["google_drive_release"][
            "readback_sha256"
        ],
        "google_drive_readback_verified": True,
        "google_drive_shared": False,
        "verified_live_revenue_events": 0,
        "external_gate_effect": "UNCHANGED",
        "full_commercial_maturity": False,
    }
    proof["proof_sha256"] = digest(proof)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    if not all(checks.values()):
        raise SystemExit(
            "authority action crash recovery release reconciliation failed"
        )
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "alpha_omega_commercial/artifacts/c15/authority-action-crash-recovery-release/reconciliation-receipt.json"
        ),
    )
    args = parser.parse_args()
    proof = run(args.output)
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
