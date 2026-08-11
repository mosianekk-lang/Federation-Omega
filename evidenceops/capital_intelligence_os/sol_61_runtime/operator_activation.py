from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class CloudRunCanarySpec:
    service: str
    region: str
    audience: str
    endpoint: str
    request_body: dict[str, Any]
    expected_readback: dict[str, Any]
    rollback_operation: str


@dataclass(frozen=True)
class AppsScriptOAuthSpec:
    script_id: str
    oauth_subject: str | None
    required_scopes: tuple[str, ...]
    standard_cloud_project_id: str
    callback_uri: str
    state_nonce: str


class OperatorActivationPackage:
    """Fail-closed activation package for live Cloud Run and Apps Script proof."""

    REQUIRED_SCOPES = (
        "https://www.googleapis.com/auth/script.projects",
        "https://www.googleapis.com/auth/script.deployments",
    )

    @staticmethod
    def cloud_run_manifest(spec: CloudRunCanarySpec) -> dict[str, Any]:
        manifest = {
            "provider": "google-cloud-run",
            "operation": "authenticated_reversible_canary",
            "spec": asdict(spec),
            "required_receipts": [
                "identity-token-subject",
                "service-revision",
                "provider-request-id",
                "response-status",
                "response-body-sha256",
                "readback-match",
                "rollback-receipt",
            ],
            "promotion_rule": "all_required_receipts_present_and_verified",
            "truth_boundary": {"live_invocation_performed": False},
        }
        manifest["sha256"] = digest(manifest)
        return manifest

    @classmethod
    def apps_script_manifest(cls, spec: AppsScriptOAuthSpec) -> dict[str, Any]:
        scopes_ok = set(cls.REQUIRED_SCOPES) <= set(spec.required_scopes)
        manifest = {
            "provider": "google-apps-script",
            "operation": "human_oauth_source_and_trigger_canary",
            "spec": asdict(spec),
            "authority_ready": bool(spec.oauth_subject and spec.callback_uri and spec.state_nonce and scopes_ok),
            "required_receipts": [
                "oauth-subject",
                "oauth-scope-set",
                "cloud-project-binding",
                "source-read-sha256",
                "source-write-revision",
                "source-readback-sha256",
                "source-restore-revision",
                "trigger-install-id",
                "trigger-delete-receipt",
            ],
            "promotion_rule": "owner_oauth_plus_complete_native_receipts",
            "truth_boundary": {
                "service_account_sufficient": False,
                "live_source_authority_proven": False,
                "owner_consent_required": not bool(spec.oauth_subject),
            },
        }
        manifest["sha256"] = digest(manifest)
        return manifest

    @staticmethod
    def evaluate_promotion(manifest: dict[str, Any], receipts: dict[str, Any]) -> dict[str, Any]:
        required = set(manifest["required_receipts"])
        missing = sorted(required - set(receipts))
        invalid = sorted(k for k in required & set(receipts) if not receipts[k])
        promoted = not missing and not invalid
        result = {
            "provider": manifest["provider"],
            "status": "LIVE_CERTIFIED" if promoted else "ACTIVATION_PENDING",
            "missing_receipts": missing,
            "invalid_receipts": invalid,
            "manifest_sha256": manifest["sha256"],
        }
        result["sha256"] = digest(result)
        return result
