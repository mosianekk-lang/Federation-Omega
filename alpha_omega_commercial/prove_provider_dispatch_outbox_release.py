from __future__ import annotations

import argparse
import json
from pathlib import Path

from authority_snapshot import digest


def prove(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent
    implementation = json.loads(
        (root / "provider_dispatch_outbox_checkpoint.json").read_text()
    )
    release = json.loads(
        (root / "provider_dispatch_outbox_release_checkpoint.json").read_text()
    )
    projection = json.loads(
        (root / "canonical_commercial_api_effective_v11.json").read_text()
    )

    provider = release["provider_proof"]
    drive = release["google_drive_release"]
    effective = release["effective_state"]
    checks = {
        "implementation_status_provider_verified": implementation["status"]
        == (
            "PROVIDER_DISPATCH_OUTBOX_PROVIDER_PROOF_VERIFIED_"
            "MOCK_CONFORMANCE_ONLY_EXTERNAL_GATES_UNCHANGED"
        ),
        "implementation_pr_and_merge_bound": implementation[
            "implementation_release"
        ]["pull_request"]
        == 139
        and implementation["implementation_release"]["merge_commit"]
        == "e8591e5212da5aba07b768aed399c79f36808b8a",
        "provider_workflow_bound": provider["workflow_run"] == 30899701403
        and provider["workflow_job"] == 91960862529,
        "provider_artifact_bound": provider["artifact_id"] == 8888531477
        and provider["artifact_digest"]
        == "sha256:7b2de5c3d36ca7d75643e8e5da122b8549df0c80279fa8182687036d78678db6",
        "provider_receipt_bound": provider["receipt_file_sha256"]
        == "81ce273ca664fee4e9635691b1ece8c170dbe41d3b8be0bb08cb09cb1e610b8e"
        and provider["receipt_sha256"]
        == "9735293346f6da13b0575b894ab315f17ecde7f651993a1be1e8864c1ae71b2c",
        "provider_checks_passed": provider["checks_required"] == 11
        and provider["checks_failed"] == 0,
        "required_regressions_passed": release["provider_native_regression"][
            "all_required_runs_success"
        ]
        is True,
        "drive_release_bound": drive["file_id"]
        == "12eJAEZ288nj5z6TZNz1F_tzgQjvZwHyzRPWAl8sZb24"
        and drive["export_sha256"]
        == "bebbbce9bc6ab45dd6f4b2018bcb53fd14bc0bb4d75ffd4d3b11849efbea6742",
        "drive_readback_private": drive["readback_verified"] is True
        and drive["shared"] is False
        and drive["owner"] == "mosianekk@gmail.com",
        "effective_v11_projection": projection["capability_revision"]
        == "AO-COMMERCIAL-PROVIDER-DISPATCH-OUTBOX-V11"
        and projection["effective_canonical_class"]
        == "ProviderDispatchOutboxCommercialControlPlane",
        "service_first_and_saas_held": effective[
            "service_enabled_platform_prioritised"
        ]
        is True
        and effective["self_service_saas_held"] is True,
        "mock_conformance_not_live_proof": effective[
            "mock_provider_contract_conformance_verified"
        ]
        is True
        and effective["live_provider_operation_proven"] is False
        and effective["distributed_provider_exactly_once_proven"] is False,
        "external_gates_unchanged": all(
            value is False for value in release["external_gates"].values()
        ),
        "verified_live_revenue_zero": release["commercial_truth"][
            "verified_live_revenue_events"
        ]
        == 0,
        "full_commercial_maturity_not_claimed": release["commercial_truth"][
            "full_commercial_maturity"
        ]
        is False,
        "owner_authority_preserved": all(
            value.startswith("OWNER_RESERVED")
            for value in release["owner_authority"].values()
        ),
    }
    receipt = {
        "control_id": "AO-COMMERCIAL-PROVIDER-DISPATCH-OUTBOX-V11-RELEASE",
        "status": (
            "PROVIDER_DISPATCH_OUTBOX_RELEASE_RECONCILIATION_"
            "PROVIDER_PROOF_VERIFIED"
        ),
        "stage_scope": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "checks": checks,
        "checks_required": len(checks),
        "checks_failed": len([value for value in checks.values() if not value]),
        "implementation_release": release["implementation_release"],
        "provider_proof": provider,
        "google_drive_release": drive,
        "effective_state": effective,
        "commercial_truth": release["commercial_truth"],
        "owner_authority": release["owner_authority"],
        "external_gate_effect": "UNCHANGED",
    }
    receipt["proof_sha256"] = digest(receipt)
    if receipt["checks_failed"]:
        raise RuntimeError("provider dispatch release reconciliation failed")
    (output / "provider-dispatch-outbox-release-receipt.json").write_text(
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
