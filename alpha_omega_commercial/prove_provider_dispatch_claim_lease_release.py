from __future__ import annotations

import argparse
import json
from pathlib import Path

from authority_snapshot import digest


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prove(output: Path) -> dict:
    root = Path(__file__).resolve().parent
    checkpoint = load(root / "provider_dispatch_claim_lease_checkpoint.json")
    contract = load(root / "provider_dispatch_claim_lease_contract.json")
    projection = load(root / "canonical_commercial_api_effective_v12.json")
    programme = load(root / "programme.json")
    institution = load(root / "institution_reconciliation_checkpoint.json")

    release = checkpoint["implementation_release"]
    proof = checkpoint["operational_proof_gate"]
    drive = checkpoint["google_drive_release"]
    truth = checkpoint["commercial_truth"]
    owner = checkpoint["owner_authority"]

    checks = {
        "release_status_is_provider_verified": checkpoint["status"]
        == "PROVIDER_DISPATCH_LOCAL_LEASE_RELEASE_RECONCILIATION_PROVIDER_PROOF_VERIFIED",
        "implementation_pr_and_merge_are_bound": release["pull_request"] == 141
        and release["merge_commit"]
        == "7e73936580bd184d07115b226e2a08f79a14de04"
        and release["merged"] is True,
        "final_head_is_bound": release["final_pull_request_head"]
        == proof["final_head_sha"]
        == "529360d829bfe3c3f65cc1f2ba4b5bfe4fd03b93",
        "final_head_provider_proof_is_bound": proof["workflow_run"] == 30903857090
        and proof["workflow_job"] == 91974252463
        and proof["artifact_id"] == 8890199911
        and proof["artifact_digest"]
        == "sha256:3682a66229adf7d3ef2d5437fcf4ebd57722e2319e203e6f204e888e66f08910"
        and proof["checks_required"] == 12
        and proof["checks_failed"] == 0,
        "all_required_final_head_regressions_are_recorded": len(
            checkpoint["final_head_regression_runs"]
        )
        == 20
        and all(
            isinstance(run, int) and run > 0
            for run in checkpoint["final_head_regression_runs"].values()
        ),
        "private_drive_release_is_read_back": drive["file_id"]
        == "16siEd0z9D97ny43B-DD4v4wYf69c0ahhUylz68LzJPo"
        and drive["readback_verified"] is True
        and drive["shared"] is False
        and drive["owner"] == "mosianekk@gmail.com",
        "drive_export_is_hash_bound": drive["export_size_bytes"] == 5959
        and drive["export_sha256"]
        == "6985d7dbaff9ac73340434d76a5314a2a92e71b5858aa5b000e1fe4f5dd81621",
        "dependency_order_is_preserved": contract["stage_scope"]
        == ["C03", "C06", "C07", "C11", "C14", "C15"]
        and checkpoint["dependency_checkpoint"][
            "programme_dependency_order_verified"
        ]
        is True,
        "effective_v12_api_is_reconciled": projection["capability_revision"]
        == "AO-COMMERCIAL-PROVIDER-DISPATCH-LEASE-V12"
        and projection["effective_canonical_class"]
        == "LeasedProviderDispatchOutboxCommercialControlPlane"
        and projection["provider_dispatch"]["local_dispatch_claim_lease"]
        == "PROVIDER_NATIVE_CI_VERIFIED",
        "service_platform_first_is_preserved": projection["service_model"]
        == "SERVICE_ENABLED_PLATFORM_FIRST"
        and projection["self_service_saas"] == "HELD",
        "canonical_programme_external_gates_remain_open_not_promoted": programme[
            "canonical_status"
        ]
        == "COMMERCIAL_READINESS_VERIFIED_EXTERNAL_MATURITY_GATES_OPEN"
        and programme["strategy"]["service_enabled_platform_first"] is True,
        "institution_scope_is_preserved": checkpoint["dependency_checkpoint"][
            "institution_state_preserved"
        ]
        is True
        and institution["institution_projection"]["P13"]
        == "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK"
        and institution["institution_projection"]["P15"]
        == "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
        "external_gates_remain_false": all(
            value is False for value in checkpoint["external_gates"].values()
        ),
        "live_provider_and_revenue_claims_remain_false": truth[
            "verified_live_revenue_events"
        ]
        == 0
        and truth["payment_provider_operation_proven"] is False
        and truth["cloud_run_operation_proven"] is False
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
        "control_id": "AO-COMMERCIAL-PROVIDER-DISPATCH-LEASE-V12-RELEASE",
        "status": checkpoint["status"],
        "stage_scope": contract["stage_scope"],
        "implementation_release": release,
        "provider_proof": proof,
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
        raise RuntimeError("provider dispatch claim lease release proof failed")
    output.mkdir(parents=True, exist_ok=True)
    (output / "provider-dispatch-claim-lease-release-receipt.json").write_text(
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
