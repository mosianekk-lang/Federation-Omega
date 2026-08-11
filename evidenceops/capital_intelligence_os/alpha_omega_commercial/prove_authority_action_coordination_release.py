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
    release = load("authority_action_coordination_release_receipt.json")
    checkpoint = load("authority_action_coordination_release_checkpoint.json")
    implementation = load("authority_action_coordination_checkpoint.json")
    api = load("canonical_commercial_api.json")
    programme = load("programme.json")
    institution = json.loads(
        (ROOT.parent / "alpha_omega_v30" / "maturity.json").read_text(
            encoding="utf-8"
        )
    )

    payload = dict(release)
    recorded_sha = payload.pop("receipt_sha256")
    controls = release["effective_controls"]
    drive = release["google_drive_release"]
    proof = release["final_head_provider_proof"]
    workflows = release["final_head_workflows"]

    checks = {
        "release_receipt_integrity": digest(payload) == recorded_sha,
        "implementation_pr_merge_bound": (
            release["dependency"]["implementation_pull_request"] == 134
            and release["dependency"]["implementation_final_head"]
            == "8c6c3a857116ecf53a5c8e1b9f91276b446e251c"
            and release["dependency"]["implementation_merge_commit"]
            == "a72713473b381e5a30c4c5b99d00213effb3ff05"
        ),
        "dependency_order_preserved": release["stage_scope"]
        == ["C03", "C11", "C12", "C13", "C15"],
        "provider_artifact_bound": (
            proof["workflow_run"] == 30891182999
            and proof["artifact_id"] == 8885094025
            and proof["artifact_digest"]
            == "sha256:74b8b6026f3d0a0192d13e2af0d4fb21bd8ab18b3893ccd64b835f2680f55de8"
            and proof["receipt_file_sha256"]
            == "2432ca65ff15875030d5d60155056030ae8498a358f6fec2ec925366c58187ae"
            and proof["receipt_sha256"]
            == "2c14b4520121955e012e8499de47cc8fecbca16c81c3915c29b04e9a3fa158fe"
            and proof["checks_required"] == 12
            and proof["checks_failed"] == 0
        ),
        "all_final_head_workflows_bound": (
            len(workflows) == 21
            and all(isinstance(value, int) and value > 0 for value in workflows.values())
            and workflows["authority_action_coordination"] == 30891182999
            and workflows["C01_C05"] == 30891183017
            and workflows["C06_C09"] == 30891183486
            and workflows["C10_C15"] == 30891185040
            and workflows["github_control_plane"] == 30891183557
            and workflows["superior_logic_ci"] == 30891184915
            and workflows["repository_leak_guard"] == 30891185231
        ),
        "drive_release_bound": (
            drive["file_id"]
            == "18vFykuY7E6okU33SJuOxn4hg9z-Cnh-pDCg6xhiZyEw"
            and drive["readback_sha256"]
            == "9d0782f5bba0b8ceb56c69abdef3b21338697ce34e78dd8c3dedc87b0e19cae3"
            and drive["readback_length"] == 4645
            and drive["readback_verified"] is True
            and drive["shared"] is False
            and drive["owner"] == "mosianekk@gmail.com"
        ),
        "checkpoint_matches_release": (
            checkpoint["implementation_release"]["pull_request"] == 134
            and checkpoint["implementation_release"]["merge_commit"]
            == release["dependency"]["implementation_merge_commit"]
            and checkpoint["implementation_release"]["release_receipt_sha256"]
            == recorded_sha
            and checkpoint["provider_proof"]["artifact_id"]
            == proof["artifact_id"]
            and checkpoint["google_drive_release"]["readback_sha256"]
            == drive["readback_sha256"]
        ),
        "implementation_checkpoint_preserved": (
            implementation["dependency_checkpoint"]["preceding_pull_request"]
            == 133
            and implementation["canonical_api_candidate"][
                "current_capability_revision"
            ]
            == "AO-COMMERCIAL-AUTHORITY-ACTION-COORDINATION-V9"
            and all(value is False for value in implementation["external_gates"].values())
        ),
        "canonical_api_bound": (
            api["current_capability_revision"]
            == "AO-COMMERCIAL-AUTHORITY-ACTION-COORDINATION-V9"
            and api["current_canonical_class"]
            == "CoordinatedJournalSafeAuthoritySnapshotCommercialControlPlane"
            and api["authority_use"]["provider_process_coordination_required"]
            is True
            and api["authority_use"][
                "concurrent_startup_can_rollback_live_transaction"
            ]
            is False
        ),
        "coordination_controls_effective": (
            controls["provider_process_coordination"] is True
            and controls["startup_cleanup_serialized"] is True
            and controls["startup_recovery_serialized"] is True
            and controls["live_authority_actions_serialized"] is True
            and controls["integrity_readback_serialized"] is True
            and controls["concurrent_startup_can_rollback_live_transaction"]
            is False
            and controls["process_crash_releases_coordination_lock"] is True
            and controls["new_action_blocked_until_recovery_complete"] is True
            and controls["distributed_provider_atomicity_proven"] is False
        ),
        "service_first_strategy_preserved": (
            release["strategy"]
            == "SERVICE_ENABLED_PLATFORM_BEFORE_SELF_SERVICE_SAAS"
            and release["self_service_saas"] == "HELD"
        ),
        "external_gates_remain_false": (
            all(value is False for value in release["external_gates"].values())
            and all(value is False for value in checkpoint["external_gates"].values())
            and not programme["external_gate_evidence"]
        ),
        "zero_revenue_and_provider_blocks_preserved": (
            release["commercial_truth"]["verified_live_revenue_events"] == 0
            and release["commercial_truth"]["cloud_run_operation_proven"]
            is False
            and release["commercial_truth"]["payment_provider_operation_proven"]
            is False
            and release["provider_boundaries"]["cloud_run"].startswith(
                "PROVIDER_BLOCKED"
            )
            and release["provider_boundaries"]["payment_provider"].startswith(
                "PROVIDER_BLOCKED"
            )
        ),
        "owner_authority_preserved": all(
            value.startswith("OWNER_RESERVED")
            for value in release["owner_authority"].values()
        ),
        "institution_external_completion_blocked": (
            institution["phases"][-1]["id"] == "P15"
            and "BLOCKED" in institution["phases"][-1]["status"]
        ),
        "full_commercial_maturity_not_claimed": (
            release["commercial_truth"]["full_commercial_maturity"] is False
            and checkpoint["commercial_truth"]["full_commercial_maturity"]
            is False
            and api["full_commercial_maturity"] is False
        ),
    }

    result: dict[str, Any] = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_id": "AO-COMMERCIAL-AUTHORITY-ACTION-COORDINATION-V9-RELEASE-PROOF",
        "status": (
            "AUTHORITY_ACTION_COORDINATION_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED"
            if all(checks.values())
            else "AUTHORITY_ACTION_COORDINATION_RELEASE_RECONCILIATION_FAILED"
        ),
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not value for value in checks.values()),
        "release_receipt_sha256": recorded_sha,
        "implementation_merge_commit": release["dependency"][
            "implementation_merge_commit"
        ],
        "provider_artifact_id": proof["artifact_id"],
        "provider_artifact_digest": proof["artifact_digest"],
        "google_drive_file_id": drive["file_id"],
        "google_drive_readback_sha256": drive["readback_sha256"],
        "google_drive_readback_verified": True,
        "google_drive_shared": False,
        "verified_live_revenue_events": 0,
        "external_gate_effect": "UNCHANGED",
        "full_commercial_maturity": False,
    }
    result["proof_sha256"] = digest(result)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not all(checks.values()):
        raise SystemExit(
            "authority action coordination release reconciliation failed"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/authority-action-coordination-release-reconciliation-receipt.json"
        ),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
