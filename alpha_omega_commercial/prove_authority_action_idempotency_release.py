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
    release = load("authority_action_idempotency_release_receipt.json")
    checkpoint = load("authority_action_idempotency_release_checkpoint.json")
    implementation = load("authority_action_idempotency_checkpoint.json")
    programme = load("programme.json")
    institution = json.loads(
        (ROOT.parent / "alpha_omega_v30" / "maturity.json").read_text(
            encoding="utf-8"
        )
    )

    payload = dict(release)
    recorded_sha = payload.pop("receipt_sha256")
    proof = release["final_head_provider_proof"]
    workflows = release["final_head_workflows"]
    drive = release["google_drive_release"]
    controls = release["effective_controls"]

    checks = {
        "release_receipt_integrity": digest(payload) == recorded_sha,
        "implementation_pr_merge_bound": (
            release["dependency"]["implementation_pull_request"] == 136
            and release["dependency"]["implementation_final_head"]
            == "4528ca39cf4a55cea12fbf89810048bb7916be14"
            and release["dependency"]["implementation_merge_commit"]
            == "31e06053764b9900f6edb8fe89a773737f1af264"
        ),
        "dependency_order_preserved": release["stage_scope"]
        == ["C03", "C11", "C12", "C13", "C15"],
        "provider_artifact_bound": (
            proof["workflow_run"] == 30895364093
            and proof["workflow_job"] == 91946871070
            and proof["artifact_id"] == 8886777639
            and proof["artifact_digest"]
            == "sha256:34611bb614558ea8218e8268deb3ccb75b33206c1d25978afaadf3c368a963da"
            and proof["receipt_sha256"]
            == "f61dc9632881d3c34363d6113516b18804264056cec7110bc0faa66284892786"
            and proof["checks_required"] == 10
            and proof["checks_failed"] == 0
        ),
        "all_final_head_workflows_bound": (
            len(workflows) == 23
            and all(isinstance(value, int) and value > 0 for value in workflows.values())
            and workflows["authority_action_idempotency"] == 30895364093
            and workflows["C01_C05"] == 30895363860
            and workflows["C06_C09"] == 30895364052
            and workflows["C10_C15"] == 30895363763
            and workflows["github_control_plane"] == 30895366467
            and workflows["superior_logic_ci"] == 30895364071
            and workflows["repository_leak_guard"] == 30895364070
        ),
        "drive_release_bound": (
            drive["file_id"]
            == "14pySl3BSQqgi0XIeuJYks6_y2EwW-Mu4mTyYCAKiR38"
            and drive["readback_sha256"]
            == "a70a6d6d938ec8769dfd25e35a8b8174be50355c5ad9f80cf425a8d7a9e019a8"
            and drive["readback_length"] == 4498
            and drive["readback_verified"] is True
            and drive["shared"] is False
            and drive["owner"] == "mosianekk@gmail.com"
        ),
        "checkpoint_matches_release": (
            checkpoint["implementation_release"]["pull_request"] == 136
            and checkpoint["implementation_release"]["merge_commit"]
            == release["dependency"]["implementation_merge_commit"]
            and checkpoint["implementation_release"]["release_receipt_sha256"]
            == recorded_sha
            and checkpoint["provider_proof"]["artifact_id"] == proof["artifact_id"]
            and checkpoint["google_drive_release"]["readback_sha256"]
            == drive["readback_sha256"]
        ),
        "implementation_checkpoint_verified": (
            implementation["status"]
            == "AUTHORITY_ACTION_IDEMPOTENCY_PROVIDER_PROOF_VERIFIED_EXTERNAL_GATES_UNCHANGED"
            and implementation["candidate_projection"]["capability_revision"]
            == "AO-COMMERCIAL-AUTHORITY-ACTION-IDEMPOTENCY-V10"
            and implementation["provider_proof"]["checks_failed"] == 0
            and all(value is False for value in implementation["external_gates"].values())
        ),
        "exact_retry_controls_effective": (
            controls["canonical_intent_hash_required"] is True
            and controls["exact_retry_returns_committed_record"] is True
            and controls["retry_consumes_owner_authority_again"] is False
            and controls["exact_retry_creates_new_transaction"] is False
            and controls["conflicting_object_identity_reuse_rejected"] is True
            and controls["idempotency_seal_transaction_bound"] is True
            and controls["restart_safe"] is True
            and controls["historical_unsealed_commit_replayed"] is False
            and controls["tampered_seal_fails_closed"] is True
            and controls["distributed_provider_exactly_once_proven"] is False
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
            and release["commercial_truth"]["cloud_run_operation_proven"] is False
            and release["commercial_truth"]["payment_provider_operation_proven"] is False
            and release["provider_boundaries"]["cloud_run"].startswith("PROVIDER_BLOCKED")
            and release["provider_boundaries"]["payment_provider"].startswith("PROVIDER_BLOCKED")
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
            and checkpoint["commercial_truth"]["full_commercial_maturity"] is False
        ),
    }

    result: dict[str, Any] = {
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "proof_id": "AO-COMMERCIAL-AUTHORITY-ACTION-IDEMPOTENCY-V10-RELEASE-PROOF",
        "status": (
            "AUTHORITY_ACTION_IDEMPOTENCY_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED"
            if all(checks.values())
            else "AUTHORITY_ACTION_IDEMPOTENCY_RELEASE_RECONCILIATION_FAILED"
        ),
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not value for value in checks.values()),
        "release_receipt_sha256": recorded_sha,
        "implementation_merge_commit": release["dependency"]["implementation_merge_commit"],
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
        raise SystemExit("authority action idempotency release reconciliation failed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/authority-action-idempotency-release-reconciliation-receipt.json"
        ),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
