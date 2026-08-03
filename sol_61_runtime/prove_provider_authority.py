from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from provider_authority import AppsScriptAuthorityEvidence, CloudRunInvocationEvidence, ProviderAuthorityGate, digest
from runtime import utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    cloud = ProviderAuthorityGate.certify_cloud_run(CloudRunInvocationEvidence(
        service="federation-omega-operator",
        revision="UNVERIFIED",
        request_id="NO_AUTHENTICATED_INVOCATION",
        authenticated_principal="",
        response_status=0,
        response_body_hash="",
        readback_match=False,
        rollback_supported=False,
    ))
    apps = ProviderAuthorityGate.certify_apps_script(AppsScriptAuthorityEvidence(
        script_id="1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R",
        oauth_subject=None,
        oauth_scopes=(),
        standard_cloud_project_bound=False,
        apps_script_api_enabled=True,
    ))
    gates = {
        "cloud_run_fail_closed_without_live_receipt": cloud["status"] == "CLOUD_RUN_CERTIFICATION_BLOCKED",
        "apps_script_owner_consent_boundary": apps["status"] == "OWNER_CONSENT_REQUIRED",
        "service_account_non_sufficiency_encoded": not apps["truth_boundary"]["service_accounts_sufficient_for_apps_script_api"],
        "human_oauth_requirement_encoded": apps["truth_boundary"]["human_oauth_required"],
        "trigger_in_script_boundary_encoded": apps["truth_boundary"]["trigger_creation_requires_in_script_execution"],
    }
    result = {
        "status": "CLOUDRUN_APPS_SCRIPT_AUTHORITY_GATE_VERIFIED" if all(gates.values()) else "CLOUDRUN_APPS_SCRIPT_AUTHORITY_GATE_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "cloud_run": cloud,
        "apps_script": apps,
        "truth_boundary": {
            "github_actions_execution": True,
            "cloud_run_live_invocation_certified": False,
            "apps_script_live_source_authority_certified": False,
            "owner_consent_still_required": True,
        },
    }
    result["sha256"] = digest(result)
    (out / "sol-61-provider-authority-receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "cloud-run-live-evidence-template.json").write_text(json.dumps({
        "service": "federation-omega-operator",
        "revision": "<provider revision>",
        "request_id": "<provider request id>",
        "authenticated_principal": "<human or workload identity>",
        "response_status": 200,
        "response_body_hash": "<sha256>",
        "readback_match": True,
        "rollback_supported": True,
    }, indent=2) + "\n", encoding="utf-8")
    (out / "apps-script-oauth-evidence-template.json").write_text(json.dumps({
        "script_id": "1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R",
        "oauth_subject": "<owner Google account>",
        "oauth_scopes": sorted(ProviderAuthorityGate.REQUIRED_APPS_SCRIPT_SCOPES),
        "standard_cloud_project_bound": True,
        "apps_script_api_enabled": True,
        "source_read_receipt": "<receipt>",
        "source_write_receipt": "<receipt>",
        "trigger_receipt": "<receipt from in-script ScriptApp execution>",
    }, indent=2) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
