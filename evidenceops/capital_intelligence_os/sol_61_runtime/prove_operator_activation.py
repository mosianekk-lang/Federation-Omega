from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from operator_activation import AppsScriptOAuthSpec, CloudRunCanarySpec, OperatorActivationPackage, digest
from runtime import utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    cloud = OperatorActivationPackage.cloud_run_manifest(CloudRunCanarySpec(
        service="federation-omega-operator",
        region="UNVERIFIED",
        audience="<cloud-run-service-url>",
        endpoint="/canary",
        request_body={"operation": "reversible_ping", "idempotency_key": "<uuid>"},
        expected_readback={"status": "ok", "rollback": "available"},
        rollback_operation="delete_canary",
    ))
    apps = OperatorActivationPackage.apps_script_manifest(AppsScriptOAuthSpec(
        script_id="1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R",
        oauth_subject=None,
        required_scopes=OperatorActivationPackage.REQUIRED_SCOPES,
        standard_cloud_project_id="sov-hybrid-suite",
        callback_uri="<owner-controlled-oauth-callback>",
        state_nonce="<cryptographic-state>",
    ))
    cloud_pending = OperatorActivationPackage.evaluate_promotion(cloud, {})
    apps_pending = OperatorActivationPackage.evaluate_promotion(apps, {})
    gates = {
        "cloud_run_manifest_complete": len(cloud["required_receipts"]) == 7,
        "apps_script_manifest_complete": len(apps["required_receipts"]) == 9,
        "cloud_run_fail_closed": cloud_pending["status"] == "ACTIVATION_PENDING",
        "apps_script_fail_closed": apps_pending["status"] == "ACTIVATION_PENDING",
        "owner_consent_preserved": apps["truth_boundary"]["owner_consent_required"],
        "service_account_boundary_preserved": not apps["truth_boundary"]["service_account_sufficient"],
    }
    result = {
        "status": "OPERATOR_ACTIVATION_PACKAGE_VERIFIED" if all(gates.values()) else "OPERATOR_ACTIVATION_PACKAGE_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "truth_boundary": {
            "github_actions_execution": True,
            "cloud_run_live_invocation_performed": False,
            "apps_script_live_source_authority_proven": False,
            "owner_consent_required": True,
        },
    }
    result["sha256"] = digest(result)
    (out / "sol-61-operator-activation-receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (out / "cloud-run-activation-manifest.json").write_text(json.dumps(cloud, indent=2, sort_keys=True) + "\n")
    (out / "apps-script-activation-manifest.json").write_text(json.dumps(apps, indent=2, sort_keys=True) + "\n")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
