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
    release = load("authority_snapshot_action_binding_release_receipt.json")
    checkpoint = load("authority_snapshot_action_binding_checkpoint.json")
    api = load("canonical_commercial_api.json")
    programme = load("programme.json")
    institution = json.loads(
        (ROOT.parent / "alpha_omega_v30" / "maturity.json").read_text(
            encoding="utf-8"
        )
    )

    receipt_payload = dict(release)
    recorded_receipt_sha = receipt_payload.pop("receipt_sha256")
    checks = {
        "release_receipt_integrity": digest(receipt_payload) == recorded_receipt_sha,
        "implementation_pr_and_merge_bound": (
            release["dependency"]["implementation_pull_request"] == 125
            and release["dependency"]["implementation_merge_commit"]
            == "03418d4317603037e85bdb282c55385e4fbb9a03"
        ),
        "dependency_order_preserved": release["stage_scope"]
        == ["C03", "C11", "C12", "C13", "C15"],
        "final_provider_artifact_bound": (
            release["final_head_provider_proof"]["workflow_run"] == 30881244285
            and release["final_head_provider_proof"]["artifact_id"] == 8881364097
            and release["final_head_provider_proof"]["artifact_digest"]
            == "sha256:99efbf9eee3f34ab64a65fb5e32a52b359d9cb889f1fcfcbfbe1f98f8e4d95e0"
            and release["final_head_provider_proof"]["checks_failed"] == 0
        ),
        "all_final_workflows_recorded": len(release["final_head_workflows"]) == 14
        and all(
            isinstance(run_id, int) and run_id > 0
            for run_id in release["final_head_workflows"].values()
        ),
        "drive_release_exactly_bound": (
            release["google_drive_release"]["file_id"]
            == "1jV7bfhfKICzEaPNmANb9o_kOfrdwq1yps3ZEkkmvv6s"
            and release["google_drive_release"]["readback_verified"] is True
            and release["google_drive_release"]["shared"] is False
            and len(release["google_drive_release"]["readback_sha256"]) == 64
        ),
        "checkpoint_matches_release": (
            checkpoint["implementation_release"]["pull_request"] == 125
            and checkpoint["implementation_release"]["merge_commit"]
            == release["dependency"]["implementation_merge_commit"]
            and checkpoint["implementation_release"]["release_receipt_sha256"]
            == recorded_receipt_sha
            and checkpoint["provider_proof"]["artifact_id"]
            == release["final_head_provider_proof"]["artifact_id"]
            and checkpoint["google_drive_release"]["file_id"]
            == release["google_drive_release"]["file_id"]
        ),
        "canonical_api_revision_bound": (
            api["api_id"] == "AO-COMMERCIAL-CANONICAL-API-V3"
            and api["capability_revision"]
            == "AO-COMMERCIAL-AUTHORITY-ACTION-BINDING-V5"
            and api["authority_use"]["action_binding_required"] is True
            and api["authority_use"]["stale_worker_view_can_authorize_action"]
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
        "no_cloud_or_payment_operation_claim": (
            release["commercial_truth"]["cloud_run_operation_proven"] is False
            and release["commercial_truth"]["payment_provider_operation_proven"]
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
        "proof_id": "AO-COMMERCIAL-AUTHORITY-ACTION-BINDING-V5-RELEASE-PROOF",
        "status": (
            "AUTHORITY_ACTION_BINDING_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED"
            if all(checks.values())
            else "AUTHORITY_ACTION_BINDING_RELEASE_RECONCILIATION_FAILED"
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
        raise SystemExit("authority action binding release reconciliation failed")
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "alpha_omega_commercial/artifacts/c15/authority-action-binding-release/reconciliation-receipt.json"
        ),
    )
    args = parser.parse_args()
    proof = run(args.output)
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
