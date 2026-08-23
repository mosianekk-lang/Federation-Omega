from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import uuid
from typing import Any, Mapping


SCHEMA = "FEDOMEGA-PROVIDER-AUTHORITY-ATTACHMENT-1"
HANDLE_SCHEMA = "FEDOMEGA-OPAQUE-CAPABILITY-HANDLE-1"
LINEAGE_SCHEMA = "FEDOMEGA-GOOGLE-IDENTITY-LINEAGE-1"
MAX_HANDLE_SECONDS = 600
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROJECT_NUMBER = re.compile(r"^[0-9]{6,20}$")

CANONICAL_PROJECT_ID = "sov-hybrid-suite"
CANONICAL_PROJECT_NUMBER = "257649435135"

KNOWN_GOOGLE_PROJECT_ROLES = {
    CANONICAL_PROJECT_NUMBER: "CANONICAL_PROVIDER_AUTHORITY_TARGET",
    "516699068552": "LEGACY_CLOUDOPS_TRANSPORT_ONLY",
    "516690968552": "CLOUDOPS_OAUTH_CONSUMER_BLOCKED",
    "979287460558": "FOGAS_OAUTH_CONSUMER_BLOCKED",
}

ROUTE_GOOGLE_CLOUD_RESOURCE_ADMIN = "GOOGLE_CLOUD_RESOURCE_ADMIN"
ROUTE_APPS_SCRIPT_PROJECT_MANAGEMENT = "APPS_SCRIPT_PROJECT_MANAGEMENT"
ROUTE_APPS_SCRIPT_SCRIPTS_RUN = "APPS_SCRIPT_SCRIPTS_RUN"
SUPPORTED_GOOGLE_ROUTE_CLASSES = {
    ROUTE_GOOGLE_CLOUD_RESOURCE_ADMIN,
    ROUTE_APPS_SCRIPT_PROJECT_MANAGEMENT,
    ROUTE_APPS_SCRIPT_SCRIPTS_RUN,
}


class AttachmentError(RuntimeError):
    """Fail-closed provider authority attachment error."""


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


@dataclass(frozen=True)
class GoogleIdentityLineageState:
    """Redacted observation of the separate Google identity lineages.

    The resource target, OAuth consumer project and transport project are
    intentionally distinct. A change to one field never repairs or verifies
    another field.
    """

    target_project_id: str
    target_project_number: str
    oauth_consumer_project_number: str
    transport_project_number: str | None = None
    route_class: str = ROUTE_GOOGLE_CLOUD_RESOURCE_ADMIN
    apps_script_api_access_granted: bool = False
    standard_cloud_project_shared: bool = False
    active_principal: str = ""
    consumer_identity_verified: bool = False
    consumer_api_enabled: bool = False
    target_authority_verified: bool = False
    token_issued: bool = False
    provider_authenticated: bool = False
    semantic_readback_verified: bool = False
    deployment_inventory_verified: bool = False
    public_web_app: bool = False
    approval_default_injected: bool = False
    credential_value_recorded: bool = False
    provider_mutation_performed: bool = False


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


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


def reject_secret_payload(value: Any, path: str = "receipt") -> None:
    forbidden_keys = {
        "secretdata",
        "payload",
        "payloaddata",
        "accesstoken",
        "refreshtoken",
        "idtoken",
        "apikey",
        "privatekey",
        "authorization",
        "credentialvalue",
    }
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).replace("_", "").lower()
            if lowered in forbidden_keys:
                raise AttachmentError(f"secret-bearing field prohibited: {path}.{key}")
            reject_secret_payload(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_secret_payload(item, f"{path}[{index}]")
    elif isinstance(value, str):
        if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", value):
            raise AttachmentError(f"secret-shaped OpenAI key at {path}")
        if re.search(r"gh[pousr]_[A-Za-z0-9_]{20,}", value):
            raise AttachmentError(f"secret-shaped GitHub token at {path}")
        private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
        if private_key_marker in value:
            raise AttachmentError(f"private key at {path}")


def _project_role(project_number: str | None) -> str:
    if not project_number:
        return "NO_PROJECT_LINEAGE"
    return KNOWN_GOOGLE_PROJECT_ROLES.get(
        str(project_number), "UNKNOWN_PROJECT_LINEAGE"
    )


def validate_google_identity_lineage(state: GoogleIdentityLineageState) -> None:
    """Validate internal consistency without upgrading any proof state."""

    reject_secret_payload(asdict(state))
    if state.credential_value_recorded:
        raise AttachmentError("credential values are prohibited")
    if not state.target_project_id:
        raise AttachmentError("target project id is required")
    if not PROJECT_NUMBER.fullmatch(str(state.target_project_number)):
        raise AttachmentError("target project number is invalid")
    if not PROJECT_NUMBER.fullmatch(str(state.oauth_consumer_project_number)):
        raise AttachmentError("OAuth consumer project number is invalid")
    if state.transport_project_number and not PROJECT_NUMBER.fullmatch(
        str(state.transport_project_number)
    ):
        raise AttachmentError("transport project number is invalid")
    if state.route_class not in SUPPORTED_GOOGLE_ROUTE_CLASSES:
        raise AttachmentError("unsupported Google route class")
    if state.provider_authenticated and not state.token_issued:
        raise AttachmentError("provider authentication requires token issuance proof")
    if state.target_authority_verified and not state.provider_authenticated:
        raise AttachmentError(
            "target authority verification requires provider authentication"
        )
    if state.semantic_readback_verified and not state.provider_authenticated:
        raise AttachmentError(
            "semantic readback requires provider authentication"
        )


def classify_google_identity_lineage(
    state: GoogleIdentityLineageState,
) -> dict[str, Any]:
    """Classify Google target, consumer and transport identity without conflation.

    This function is provider-neutral control logic only. It performs no
    provider call, mutation, API enablement, token exchange or deployment.
    """

    validate_google_identity_lineage(state)

    target_role = _project_role(state.target_project_number)
    consumer_role = _project_role(state.oauth_consumer_project_number)
    transport_role = _project_role(state.transport_project_number)
    canonical_target = (
        state.target_project_id == CANONICAL_PROJECT_ID
        and state.target_project_number == CANONICAL_PROJECT_NUMBER
    )
    base_consumer_binding_ready = (
        state.consumer_identity_verified and state.consumer_api_enabled
    )
    consumer_target_same = (
        state.oauth_consumer_project_number == state.target_project_number
    )
    if state.route_class == ROUTE_APPS_SCRIPT_SCRIPTS_RUN:
        route_relationship_ready = all(
            (
                state.apps_script_api_access_granted,
                state.standard_cloud_project_shared,
                consumer_target_same,
            )
        )
        route_relationship_rule = (
            "CALLER_AND_SCRIPT_MUST_SHARE_COMMON_STANDARD_CLOUD_PROJECT"
        )
    elif state.route_class == ROUTE_APPS_SCRIPT_PROJECT_MANAGEMENT:
        route_relationship_ready = state.apps_script_api_access_granted
        route_relationship_rule = (
            "APPS_SCRIPT_API_ACCESS_GRANT_AND_CONSUMER_API_ENABLEMENT_REQUIRED"
        )
    else:
        route_relationship_ready = True
        route_relationship_rule = (
            "CONSUMER_MAY_DIFFER_BUT_TARGET_AUTHORITY_REQUIRES_SEPARATE_PROOF"
        )
    consumer_binding_ready = (
        base_consumer_binding_ready and route_relationship_ready
    )
    public_approval_bypass = (
        state.public_web_app and state.approval_default_injected
    )

    provider_authority_ready = all(
        (
            canonical_target,
            consumer_binding_ready,
            state.target_authority_verified,
            state.token_issued,
            state.provider_authenticated,
            state.semantic_readback_verified,
            state.deployment_inventory_verified,
            bool(state.active_principal),
            not public_approval_bypass,
        )
    )

    unexpected_mutation = (
        state.provider_mutation_performed and not provider_authority_ready
    )

    if unexpected_mutation:
        status = "PROVIDER_MUTATION_WITHOUT_AUTHORITY_PROOF"
        next_gate = "CONTAIN_PRESERVE_AND_INDEPENDENTLY_READ_BACK"
    elif public_approval_bypass:
        status = "SECURITY_HOLD_PUBLIC_APPROVAL_BYPASS"
        next_gate = "PATCH_AUTHORIZATION_AND_RUN_NEGATIVE_UNAUTHORIZED_CANARY"
    elif not canonical_target:
        status = "BLOCKED_CANONICAL_TARGET_MISMATCH"
        next_gate = "RESTORE_CANONICAL_TARGET_WITHOUT_REBINDING_ASSUMPTIONS"
    elif not base_consumer_binding_ready:
        status = "BLOCKED_OAUTH_CONSUMER_BINDING"
        next_gate = "VERIFY_CONSUMER_IDENTITY_AND_ENABLE_REQUIRED_API_IN_CONSUMER"
    elif not route_relationship_ready:
        status = "BLOCKED_ROUTE_PROJECT_RELATIONSHIP"
        next_gate = "REPAIR_ROUTE_SPECIFIC_PROJECT_AND_API_BINDING"
    elif not (
        state.token_issued
        and state.provider_authenticated
        and state.target_authority_verified
        and bool(state.active_principal)
    ):
        status = "AUTHENTICATED_ADMIN_RECOVERY_PENDING"
        next_gate = "ISSUE_TOKEN_AND_READ_BACK_PRINCIPAL_TARGET_AND_SCOPE"
    elif not state.semantic_readback_verified:
        status = "SEMANTIC_PROVIDER_READBACK_PENDING"
        next_gate = "RUN_ACTION_SPECIFIC_READ_ONLY_CANARY"
    elif not state.deployment_inventory_verified:
        status = "DEPLOYMENT_INVENTORY_PENDING"
        next_gate = "READ_BACK_DEPLOYMENTS_AND_NEGATIVE_UNAUTHORIZED_PATH"
    else:
        status = "PROVIDER_AUTHORITY_VERIFIED"
        next_gate = "ISSUE_BOUNDED_READ_ONLY_HANDLE"

    payload = {
        "schema": LINEAGE_SCHEMA,
        "status": status,
        "target": {
            "project_id": state.target_project_id,
            "project_number": state.target_project_number,
            "role": target_role,
            "canonical_match": canonical_target,
            "authority_verified": state.target_authority_verified,
        },
        "oauth_consumer": {
            "project_number": state.oauth_consumer_project_number,
            "role": consumer_role,
            "identity_verified": state.consumer_identity_verified,
            "required_api_enabled": state.consumer_api_enabled,
            "base_binding_ready": base_consumer_binding_ready,
            "binding_ready": consumer_binding_ready,
        },
        "route": {
            "route_class": state.route_class,
            "apps_script_api_access_granted": (
                state.apps_script_api_access_granted
            ),
            "standard_cloud_project_shared": (
                state.standard_cloud_project_shared
            ),
            "consumer_target_same": consumer_target_same,
            "relationship_ready": route_relationship_ready,
            "relationship_rule": route_relationship_rule,
        },
        "transport": {
            "project_number": state.transport_project_number,
            "role": transport_role,
            "legacy_transport_reuse_only": (
                transport_role == "LEGACY_CLOUDOPS_TRANSPORT_ONLY"
            ),
            "authority_inherited": False,
        },
        "principal": {
            "present": bool(state.active_principal),
            "token_issued": state.token_issued,
            "provider_authenticated": state.provider_authenticated,
        },
        "proof": {
            "semantic_readback_verified": state.semantic_readback_verified,
            "deployment_inventory_verified": state.deployment_inventory_verified,
            "provider_mutation_performed": state.provider_mutation_performed,
        },
        "security": {
            "public_web_app": state.public_web_app,
            "approval_default_injected": state.approval_default_injected,
            "public_approval_bypass": public_approval_bypass,
        },
        "invariants": {
            "target_change_repairs_oauth_consumer": False,
            "transport_success_grants_provider_authority": False,
            "consumer_project_must_equal_target_project": (
                state.route_class == ROUTE_APPS_SCRIPT_SCRIPTS_RUN
            ),
            "consumer_and_target_require_separate_verification": True,
            "route_specific_project_relationships_are_enforced": True,
        },
        "provider_authority_ready": provider_authority_ready,
        "next_gate": next_gate,
        "provider_mutation_authorized_by_this_receipt": False,
        "credential_value_recorded": False,
        "truth_boundary": (
            "A resource target, OAuth consumer and transport project are "
            "separate identity lineages. Only token/principal, target authority, "
            "semantic readback and deployment/security proof can promote "
            "provider authority."
        ),
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
