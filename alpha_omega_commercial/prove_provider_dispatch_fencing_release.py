from __future__ import annotations

import argparse
import json
from pathlib import Path

from authority_snapshot import digest


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prove(output: Path) -> dict:
    root = Path(__file__).resolve().parent
    checkpoint = load(root / "provider_dispatch_fencing_checkpoint.json")
    contract = load(root / "provider_dispatch_fencing_contract.json")
    projection = load(root / "canonical_commercial_api_effective_v13.json")
    programme = load(root / "programme.json")
    institution = load(root / "institution_reconciliation_checkpoint.json")
    stages = {stage["id"]: stage for stage in programme["stages"]}

    release = checkpoint["implementation_release"]
    proof = checkpoint["operational_proof_gate"]
    drive = checkpoint["google_drive_release"]
    truth = checkpoint["commercial_truth"]
    owner = checkpoint["owner_authority"]
    regression_runs = checkpoint["final_head_regression_runs"]

    checks = {
        "release_status_is_provider_verified": checkpoint["status"]
        == "PROVIDER_DISPATCH_RENEWAL_AND_FENCING_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED",
        "implementation_and_proof_pr_are_bound": release["implementation_head"]
        == "8d6080a34cd95138ac72f07a0b5eadbb366c28ff"
        and release["provider_proof_pull_request"] == 144
        and release["final_pull_request_head"]
        == "9b3dd3912104add4f696a08d489dcdbd77145ece"
        and release["merge_commit"]
        == "e4f2eb27e6e32289dd2ab759f760c6c2ad7046bf"
        and release["merged"] is True,
        "final_head_provider_proof_is_bound": proof["final_head_sha"]
        == release["final_pull_request_head"]
        and proof["workflow_run"] == 30908421554
        and proof["workflow_job"] == 91988902372
        and proof["artifact_id"] == 8892003824
        and proof["artifact_digest"]
        == "sha256:93cc9cc29dca88d2ed883e5784f3065b566d260417931c31436d056af028fa60"
        and proof["proof_receipt_file_sha256"]
        == "937a8f80db646d9af604b38d639f897dadff8744004382888354dcfef77a5dec"
        and proof["proof_receipt_sha256"]
        == "281d8fa441e7620411e5ab6a683af97958ae0c529d014dc3a9cce5000e2e8354"
        and proof["checks_required"] == 12
        and proof["checks_failed"] == 0
        and proof["job_steps_readback_verified"] is True,
        "provider_native_ci_proves_local_controls_only": proof["tests"]
        == "PROVIDER_NATIVE_CI_VERIFIED"
        and proof["mock_provider_fencing_conformance"]
        == "PROVIDER_NATIVE_CI_VERIFIED"
        and proof["lease_renewal"] == "PROVIDER_NATIVE_CI_VERIFIED"
        and proof["monotonic_dispatch_fencing"]
        == "PROVIDER_NATIVE_CI_VERIFIED"
        and proof["provider_native_fencing"] == "PROVIDER_PROOF_REQUIRED"
        and proof["live_provider_receipt"] == "PROVIDER_PROOF_REQUIRED"
        and proof["external_mutation_performed"] is False,
        "all_required_final_head_regressions_are_recorded": len(regression_runs)
        == 28
        and all(isinstance(run, int) and run > 0 for run in regression_runs.values())
        and regression_runs["provider_dispatch_fencing"] == 30908421554
        and regression_runs["superior_logic_ci"] == 30908423704
        and regression_runs["repository_leak_guard"] == 30908423726,
        "private_drive_release_is_read_back": drive["file_id"]
        == "1fHoNNFkbk4lQR220g46nF89Lf_LcicVYMCT9sTaHGrE"
        and drive["readback_verified"] is True
        and drive["shared"] is False
        and drive["owner"] == "mosianekk@gmail.com",
        "drive_export_is_hash_bound": drive["export_size_bytes"] == 6345
        and drive["export_sha256"]
        == "83d3b14e3151be44e513addbc967d6c2588df76a768dfc158958cc3602839a50",
        "dependency_order_is_preserved": contract["stage_scope"]
        == ["C03", "C06", "C07", "C11", "C14", "C15"]
        and checkpoint["dependency_checkpoint"][
            "programme_dependency_order_verified"
        ]
        is True,
        "effective_v13_api_is_reconciled": projection["capability_revision"]
        == "AO-COMMERCIAL-PROVIDER-DISPATCH-FENCING-V13"
        and projection["effective_canonical_class"]
        == "FencedProviderDispatchCommercialControlPlane"
        and projection["provider_dispatch"][
            "local_lease_renewal_and_fencing"
        ]
        == "PROVIDER_NATIVE_CI_VERIFIED"
        and projection["provider_dispatch"]["provider_native_fencing"]
        == "PROVIDER_PROOF_REQUIRED",
        "projection_proof_and_drive_are_bound": projection["provider_proof"][
            "workflow_run"
        ]
        == proof["workflow_run"]
        and projection["provider_proof"]["artifact_id"] == proof["artifact_id"]
        and projection["google_drive_release"]["file_id"] == drive["file_id"]
        and projection["google_drive_release"]["readback_verified"] is True
        and projection["google_drive_release"]["shared"] is False,
        "service_platform_first_is_preserved": projection["service_model"]
        == "SERVICE_ENABLED_PLATFORM_FIRST"
        and projection["self_service_saas"] == "HELD"
        and "service-enabled platform" in programme["objective"]
        and "before promoting self-service SaaS" in programme["objective"],
        "canonical_programme_external_gates_remain_open_not_promoted": programme[
            "canonical_status"
        ]
        == "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
        and stages["C11"]["status"]
        == "SERVICE_ENABLED_PLATFORM_VERIFIED_CANONICAL_CLOUD_ROUTE_ALIGNED_SELF_SERVICE_HELD"
        and stages["C15"]["status"]
        == "COMMERCIAL_READINESS_VERIFIED_CANONICAL_PROVIDER_ROUTE_ALIGNED_EXTERNAL_MATURITY_GATES_OPEN",
        "institution_scope_is_preserved": checkpoint["dependency_checkpoint"][
            "institution_state_preserved"
        ]
        is True
        and checkpoint["institution_projection"]["P13"]
        == "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK"
        and checkpoint["institution_projection"]["P15"]
        == "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED"
        and institution["institution_projection"]["P13"]
        == "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK"
        and institution["institution_projection"]["P15"]
        == "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
        "external_gates_remain_false": all(
            value is False for value in checkpoint["external_gates"].values()
        ),
        "provider_and_revenue_claims_remain_false": truth[
            "verified_live_revenue_events"
        ]
        == 0
        and truth["payment_provider_operation_proven"] is False
        and truth["cloud_run_operation_proven"] is False
        and truth["provider_native_fencing_proven"] is False
        and truth["distributed_provider_exactly_once_proven"] is False,
        "full_commercial_maturity_is_not_claimed": truth[
            "full_commercial_maturity"
        ]
        is False,
        "owner_reserved_authority_is_preserved": owner["financial_commitments"]
        == "OWNER_RESERVED"
        and owner["contracts"] == "OWNER_RESERVED"
        and owner["external_communications"] == "OWNER_RESERVED"
        and owner["consequential_releases"] == "OWNER_RESERVED"
        and owner["revenue_recognition"]
        == "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
    }

    receipt = {
        "control_id": "AO-COMMERCIAL-PROVIDER-DISPATCH-FENCING-V13-RELEASE",
        "status": checkpoint["status"],
        "stage_scope": contract["stage_scope"],
        "implementation_release": release,
        "provider_proof": proof,
        "final_head_regression_runs": regression_runs,
        "google_drive_release": drive,
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": sum(not value for value in checks.values()),
        "commercial_truth": truth,
        "owner_authority": owner,
        "external_gate_effect": "UNCHANGED",
    }
    receipt["receipt_sha256"] = digest(receipt)
    if receipt["checks_failed"]:
        raise RuntimeError("provider dispatch fencing release proof failed")
    output.mkdir(parents=True, exist_ok=True)
    (output / "provider-dispatch-fencing-release-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    print(json.dumps(prove(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
