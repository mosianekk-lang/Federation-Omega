from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import uuid
from typing import Any, Mapping

from federation_consolidation.google_identity_lineage import (
    AttachmentError,
    CANONICAL_PROJECT_ID,
    CANONICAL_PROJECT_NUMBER,
    GoogleIdentityLineageState,
    KNOWN_GOOGLE_PROJECT_ROLES,
    LINEAGE_SCHEMA,
    ROUTE_APPS_SCRIPT_ADMIN_COMPOSITE,
    ROUTE_APPS_SCRIPT_PROJECT_MANAGEMENT,
    ROUTE_APPS_SCRIPT_SCRIPTS_RUN,
    ROUTE_GOOGLE_CLOUD_RESOURCE_ADMIN,
    SUPPORTED_GOOGLE_ROUTE_CLASSES,
    canonical_sha256,
    classify_google_identity_lineage,
    reject_secret_payload,
    validate_google_identity_lineage,
)

SCHEMA = "FEDOMEGA-PROVIDER-AUTHORITY-ATTACHMENT-1"
HANDLE_SCHEMA = "FEDOMEGA-OPAQUE-CAPABILITY-HANDLE-1"
MAX_HANDLE_SECONDS = 600
HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class AttachmentState:
    active_account: str
    expected_account: str
    project_id: str
    expected_project_id: str
    project_number: str
    expected_project_number: str
    service_usage_enabled: bool
    secret_manager_enabled: bool
    cloud_run_enabled: bool
    cloud_build_enabled: bool
    metadata_probe_passed: bool
    sealed_packet_sha256: str
    sealed_packet_verified: bool
    openai_existing_key_management_available: bool
    credential_value_recorded: bool = False


def validate_state(state: AttachmentState) -> None:
    if state.credential_value_recorded:
        raise AttachmentError("credential values are prohibited")
    if state.active_account != state.expected_account:
        raise AttachmentError("active account mismatch")
    if state.project_id != state.expected_project_id:
        raise AttachmentError("project id mismatch")
    if state.project_number != state.expected_project_number:
        raise AttachmentError("project number mismatch")
    if not HEX64.fullmatch(state.sealed_packet_sha256):
        raise AttachmentError("sealed packet SHA-256 is invalid")


def build_plan(state: AttachmentState) -> dict[str, Any]:
    validate_state(state)
    services_ready = all(
        (
            state.service_usage_enabled,
            state.secret_manager_enabled,
            state.cloud_run_enabled,
            state.cloud_build_enabled,
        )
    )
    provider_read_ready = services_ready and state.metadata_probe_passed
    payload = {
        "schema": SCHEMA,
        "identity": {
            "account": state.active_account,
            "project_id": state.project_id,
            "project_number": state.project_number,
        },
        "sealed_packet": {
            "sha256": state.sealed_packet_sha256,
            "verified": state.sealed_packet_verified,
        },
        "services_ready": services_ready,
        "metadata_probe_passed": state.metadata_probe_passed,
        "provider_read_ready": provider_read_ready,
        "openai_existing_key_management_available": (
            state.openai_existing_key_management_available
        ),
        "next_gate": (
            "ISSUE_READ_ONLY_HANDLE"
            if provider_read_ready and state.sealed_packet_verified
            else "ENABLE_REQUIRED_SERVICES"
            if not services_ready
            else "RUN_METADATA_ONLY_PROBE"
            if not state.metadata_probe_passed
            else "VERIFY_SEALED_PACKET"
        ),
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def verify_metadata_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    reject_secret_payload(receipt)
    checks = {
        "secret_payload_accessed": receipt.get("secret_payload_accessed") is False,
        "raw_environment_recorded": receipt.get("raw_environment_recorded") is False,
        "provider_mutation_performed": (
            receipt.get("provider_mutation_performed") is False
        ),
        "secret_metadata_count": isinstance(
            receipt.get("secret_metadata"), list
        ) and len(receipt.get("secret_metadata", [])) >= 2,
        "cloud_run_metadata_present": isinstance(
            receipt.get("cloud_run_metadata"), dict
        ),
        "identity_present": bool(receipt.get("active_account")),
        "project_present": bool(receipt.get("project_id")),
    }
    failed = sorted(key for key, value in checks.items() if not value)
    result = {
        "status": "VERIFIED" if not failed else "BLOCKED",
        "checks": checks,
        "failed_checks": failed,
        "credential_value_recorded": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def issue_read_only_handle(
    *,
    capability_id: str,
    requester_id: str,
    mission_id: str,
    provider_reference: str,
    metadata_receipt_sha256: str,
    lifetime_seconds: int = MAX_HANDLE_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not 1 <= lifetime_seconds <= MAX_HANDLE_SECONDS:
        raise AttachmentError("handle lifetime exceeds maximum")
    if not HEX64.fullmatch(metadata_receipt_sha256):
        raise AttachmentError("metadata receipt SHA-256 invalid")
    current = now or datetime.now(timezone.utc)
    payload = {
        "schema": HANDLE_SCHEMA,
        "handle_id": f"FOSC-{uuid.uuid4()}",
        "capability_id": capability_id,
        "requester_id": requester_id,
        "mission_id": mission_id,
        "provider_reference": provider_reference,
        "scope": "READ_ONLY_PROVIDER_METADATA",
        "authority_class": "A1_PROVIDER_READ",
        "issued_at": current.isoformat(),
        "expires_at": (
            current + timedelta(seconds=lifetime_seconds)
        ).isoformat(),
        "revocation_state": "ACTIVE",
        "secret_exposed": False,
        "metadata_receipt_sha256": metadata_receipt_sha256,
        "status": "BROKER_ISSUED_READ_ONLY",
        "provider_mutation_performed": False,
    }
    payload["handle_record_sha256"] = canonical_sha256(payload)
    return payload


def revoke_handle(
    handle: Mapping[str, Any],
    *,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    reject_secret_payload(handle)
    if handle.get("schema") != HANDLE_SCHEMA:
        raise AttachmentError("handle schema mismatch")
    payload = dict(handle)
    payload["revocation_state"] = "REVOKED"
    payload["revoked_at"] = (now or datetime.now(timezone.utc)).isoformat()
    payload["revocation_reason"] = reason
    payload["status"] = "REVOKED"
    payload["handle_record_sha256"] = canonical_sha256(
        {k: v for k, v in payload.items() if k != "handle_record_sha256"}
    )
    return payload
