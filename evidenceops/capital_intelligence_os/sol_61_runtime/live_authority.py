from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class CanonicalLiveAuthority:
    REQUIRED_ROOT_KEYS = {
        "manifest_id",
        "owner",
        "canonical_sources",
        "cloud_run",
        "apps_script",
        "supporting_routes",
        "certified_reversible_surfaces",
        "owner_reserved",
        "retired_or_noncanonical_routes",
        "promotion_rule",
    }

    def __init__(self, manifest: dict[str, Any]) -> None:
        self.manifest = manifest

    @classmethod
    def from_file(cls, path: str | Path) -> "CanonicalLiveAuthority":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def validate(self) -> dict[str, Any]:
        m = self.manifest
        missing_root = sorted(self.REQUIRED_ROOT_KEYS - set(m))
        cloud = m.get("cloud_run", {})
        apps = m.get("apps_script", {})
        supporting = m.get("supporting_routes", {})

        gates = {
            "root_contract_complete": not missing_root,
            "cloud_run_single_canonical_service": all(
                bool(cloud.get(k)) for k in ("project_id", "region", "service", "path")
            ),
            "cloud_run_fail_closed": cloud.get("status") != "VERIFIED_LIVE",
            "cloud_run_receipts_complete": set(
                cloud.get("promotion_receipts", [])
            ) >= {
                "provider_revision",
                "request_id",
                "authenticated_principal",
                "response_status",
                "response_body_sha256",
                "readback_match",
                "rollback_receipt",
            },
            "apps_script_human_oauth_required": apps.get("required_identity") == "human_google_oauth_subject",
            "apps_script_service_account_rejected": apps.get("service_accounts_sufficient") is False,
            "apps_script_fail_closed": apps.get("status") in {
                "OWNER_CONSENT_REQUIRED",
                "AUTHORITY_READY_EXECUTION_UNPROVEN",
            },
            "apps_script_restore_and_trigger_cleanup_required": {
                "SOURCE_RESTORE",
                "TRIGGER_DELETE",
            } <= set(apps.get("required_sequence", [])),
            "queue_routes_not_promoted": all(
                supporting.get(name, {}).get("status") != "VERIFIED_LIVE"
                for name in ("fo_gas", "architron", "genesis")
            ),
            "verified_surfaces_declared": {
                "github",
                "google_drive",
                "gmail_draft",
                "google_calendar",
                "outlook_draft",
                "canva_transaction",
            } <= set(m.get("certified_reversible_surfaces", [])),
            "owner_boundaries_present": {
                "external_send",
                "financial_commitment",
                "contract_execution",
                "consequential_release",
                "credential_mutation",
            } <= set(m.get("owner_reserved", [])),
            "false_completion_routes_retired": {
                "pending_queue_as_execution_proof",
                "historical_heartbeat_as_current_health",
                "schema_valid_command_without_semantic_readback",
            } <= set(m.get("retired_or_noncanonical_routes", [])),
        }

        status = "CANONICAL_LIVE_AUTHORITY_MANIFEST_VERIFIED" if all(gates.values()) else "CANONICAL_LIVE_AUTHORITY_MANIFEST_FAILED"
        receipt = {
            "status": status,
            "manifest_id": m.get("manifest_id"),
            "gates": gates,
            "missing_root_keys": missing_root,
            "cloud_run_status": cloud.get("status"),
            "apps_script_status": apps.get("status"),
            "truth_boundary": {
                "github_actions_execution": True,
                "manifest_consolidated": True,
                "cloud_run_live_invocation_certified": False,
                "apps_script_live_source_authority_certified": False,
                "owner_reserved_actions_bypassed": False,
            },
        }
        receipt["sha256"] = digest(receipt)
        return receipt
