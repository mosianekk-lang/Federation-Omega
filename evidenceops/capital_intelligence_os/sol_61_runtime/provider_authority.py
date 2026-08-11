from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class CloudRunInvocationEvidence:
    service: str
    revision: str
    request_id: str
    authenticated_principal: str
    response_status: int
    response_body_hash: str
    readback_match: bool
    rollback_supported: bool


@dataclass(frozen=True)
class AppsScriptAuthorityEvidence:
    script_id: str
    oauth_subject: str | None
    oauth_scopes: tuple[str, ...]
    standard_cloud_project_bound: bool
    apps_script_api_enabled: bool
    source_read_receipt: str | None = None
    source_write_receipt: str | None = None
    trigger_receipt: str | None = None


class ProviderAuthorityGate:
    REQUIRED_APPS_SCRIPT_SCOPES = {
        "https://www.googleapis.com/auth/script.projects",
        "https://www.googleapis.com/auth/script.deployments",
    }

    @staticmethod
    def certify_cloud_run(e: CloudRunInvocationEvidence) -> dict[str, Any]:
        gates = {
            "service_identified": bool(e.service and e.revision),
            "authenticated_principal": bool(e.authenticated_principal),
            "successful_response": 200 <= e.response_status < 300,
            "response_hash": len(e.response_body_hash) == 64,
            "readback_match": e.readback_match,
            "rollback_declared": e.rollback_supported,
        }
        status = "CLOUD_RUN_LIVE_CERTIFIED" if all(gates.values()) else "CLOUD_RUN_CERTIFICATION_BLOCKED"
        receipt = {"status": status, "gates": gates, "evidence": asdict(e)}
        receipt["sha256"] = digest(receipt)
        return receipt

    @classmethod
    def certify_apps_script(cls, e: AppsScriptAuthorityEvidence) -> dict[str, Any]:
        scopes = set(e.oauth_scopes)
        authority_gates = {
            "human_oauth_subject": bool(e.oauth_subject),
            "required_oauth_scopes": cls.REQUIRED_APPS_SCRIPT_SCOPES <= scopes,
            "standard_cloud_project_bound": e.standard_cloud_project_bound,
            "apps_script_api_enabled": e.apps_script_api_enabled,
        }
        execution_gates = {
            "source_read_receipt": bool(e.source_read_receipt),
            "source_write_receipt": bool(e.source_write_receipt),
            "trigger_receipt": bool(e.trigger_receipt),
        }
        if not all(authority_gates.values()):
            status = "OWNER_CONSENT_REQUIRED"
        elif not all(execution_gates.values()):
            status = "AUTHORITY_READY_EXECUTION_UNPROVEN"
        else:
            status = "APPS_SCRIPT_LIVE_CERTIFIED"
        receipt = {
            "status": status,
            "authority_gates": authority_gates,
            "execution_gates": execution_gates,
            "evidence": asdict(e),
            "truth_boundary": {
                "service_accounts_sufficient_for_apps_script_api": False,
                "human_oauth_required": True,
                "trigger_creation_requires_in_script_execution": True,
            },
        }
        receipt["sha256"] = digest(receipt)
        return receipt
