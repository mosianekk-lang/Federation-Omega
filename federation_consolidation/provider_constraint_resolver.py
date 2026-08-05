from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping


SCHEMA = "FEDOMEGA-PROVIDER-CONSTRAINT-RESOLVER-1"


class ResolverError(RuntimeError):
    """Fail-closed provider constraint resolution error."""


class ResolutionState(StrEnum):
    RESOLVED = "RESOLVED"
    ELIMINATED_BY_ALTERNATE_ROUTE = "ELIMINATED_BY_ALTERNATE_ROUTE"
    PROVIDER_AUTHORITY_REQUIRED = "PROVIDER_AUTHORITY_REQUIRED"
    READY_FOR_FRESH_AUTHORITY = "READY_FOR_FRESH_AUTHORITY"
    BLOCKED = "BLOCKED"


class ExecutionRoute(StrEnum):
    PRIVATE_GITHUB_OPS_WIF = "PRIVATE_GITHUB_OPS_WIF"
    GCP_NATIVE_SEALED_ARTIFACT = "GCP_NATIVE_SEALED_ARTIFACT"
    OWNER_ONLY_SEALED_PACKET = "OWNER_ONLY_SEALED_PACKET"
    NONE = "NONE"


@dataclass(frozen=True)
class ProviderState:
    live_main: str
    phoenix_artifact_sha256: str
    previous_main: str
    previous_phoenix_artifact_sha256: str
    github_installation_scope: str
    private_core_visible: bool
    private_ops_visible: bool
    private_github_admin_authority: bool
    gcp_admin_authority: bool
    gcp_native_runner_available: bool
    sealed_owner_artifact_available: bool
    openai_existing_key_management_available: bool
    current_candidate_sha256: str
    candidate_bound_to_live_main: bool
    candidate_bound_to_artifact: bool
    credential_value_recorded: bool = False


@dataclass(frozen=True)
class ConstraintResult:
    constraint_id: str
    state: str
    reason: str
    selected_route: str
    next_gate: str
    provider_mutation_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _require_sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise ResolverError(f"{name} must be a lowercase SHA-256")


def _require_sha1(value: str, name: str) -> None:
    if len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise ResolverError(f"{name} must be a lowercase Git SHA")


def validate_state(state: ProviderState) -> None:
    _require_sha1(state.live_main, "live_main")
    _require_sha1(state.previous_main, "previous_main")
    _require_sha256(state.phoenix_artifact_sha256, "phoenix_artifact_sha256")
    _require_sha256(
        state.previous_phoenix_artifact_sha256,
        "previous_phoenix_artifact_sha256",
    )
    _require_sha256(state.current_candidate_sha256, "current_candidate_sha256")
    if state.credential_value_recorded:
        raise ResolverError("credential values are prohibited")
    if state.private_core_visible != state.private_ops_visible:
        raise ResolverError("partial private Core/Ops topology is inadmissible")


def detect_edges(state: ProviderState) -> list[str]:
    edges: list[str] = []
    if state.live_main != state.previous_main:
        edges.append("LIVE_MAIN_CHANGED")
    if state.phoenix_artifact_sha256 != state.previous_phoenix_artifact_sha256:
        edges.append("PHOENIX_ARTIFACT_CHANGED")
    if state.github_installation_scope.lower() not in {"selected", "all"}:
        edges.append("GITHUB_INSTALLATION_SCOPE_UNKNOWN")
    if state.private_core_visible and state.private_ops_visible:
        edges.append("PRIVATE_CORE_OPS_VISIBLE")
    if state.private_github_admin_authority:
        edges.append("PRIVATE_GITHUB_ADMIN_AUTHORITY_AVAILABLE")
    if state.gcp_admin_authority:
        edges.append("GCP_ADMIN_AUTHORITY_AVAILABLE")
    if state.gcp_native_runner_available:
        edges.append("GCP_NATIVE_RUNNER_AVAILABLE")
    if state.openai_existing_key_management_available:
        edges.append("OPENAI_EXISTING_KEY_MANAGEMENT_AVAILABLE")
    return edges


def select_execution_route(state: ProviderState) -> ExecutionRoute:
    if (
        state.private_core_visible
        and state.private_ops_visible
        and state.private_github_admin_authority
        and state.gcp_admin_authority
    ):
        return ExecutionRoute.PRIVATE_GITHUB_OPS_WIF
    if (
        state.gcp_admin_authority
        and state.gcp_native_runner_available
        and state.sealed_owner_artifact_available
    ):
        return ExecutionRoute.GCP_NATIVE_SEALED_ARTIFACT
    if state.sealed_owner_artifact_available:
        return ExecutionRoute.OWNER_ONLY_SEALED_PACKET
    return ExecutionRoute.NONE


def resolve_constraints(state: ProviderState) -> dict[str, Any]:
    validate_state(state)
    edges = detect_edges(state)
    route = select_execution_route(state)
    results: list[ConstraintResult] = []

    drift_ok = state.candidate_bound_to_live_main and state.candidate_bound_to_artifact
    results.append(
        ConstraintResult(
            constraint_id="LIVE_MAIN_OR_ARTIFACT_DRIFT",
            state=(ResolutionState.RESOLVED.value if drift_ok else ResolutionState.BLOCKED.value),
            reason=(
                "Candidate is bound to the live main and matching Phoenix artifact."
                if drift_ok
                else "Candidate must be regenerated before any authority check."
            ),
            selected_route=route.value,
            next_gate=("AUTHORITY_CHECK" if drift_ok else "REGENERATE_JUST_IN_TIME_CANDIDATE"),
        )
    )

    private_plane_ready = state.private_core_visible and state.private_ops_visible
    private_plane_eliminated = route in {
        ExecutionRoute.GCP_NATIVE_SEALED_ARTIFACT,
        ExecutionRoute.OWNER_ONLY_SEALED_PACKET,
    }
    results.append(
        ConstraintResult(
            constraint_id="PRIVATE_CORE_OPS_VISIBILITY",
            state=(
                ResolutionState.RESOLVED.value
                if private_plane_ready
                else ResolutionState.ELIMINATED_BY_ALTERNATE_ROUTE.value
                if private_plane_eliminated
                else ResolutionState.PROVIDER_AUTHORITY_REQUIRED.value
            ),
            reason=(
                "Private Core/Ops topology is visible."
                if private_plane_ready
                else "A sealed owner artifact supplies the private execution payload."
                if private_plane_eliminated
                else "No private topology or sealed execution payload is available."
            ),
            selected_route=route.value,
            next_gate=(
                "GCP_IDENTITY_AND_READBACK"
                if private_plane_ready or private_plane_eliminated
                else "CREATE_PRIVATE_PLANE_OR_SEAL_ARTIFACT"
            ),
        )
    )

    github_admin_needed = route == ExecutionRoute.PRIVATE_GITHUB_OPS_WIF
    results.append(
        ConstraintResult(
            constraint_id="PRIVATE_GITHUB_ADMIN_AUTHORITY",
            state=(
                ResolutionState.RESOLVED.value
                if state.private_github_admin_authority
                else ResolutionState.ELIMINATED_BY_ALTERNATE_ROUTE.value
                if not github_admin_needed
                else ResolutionState.PROVIDER_AUTHORITY_REQUIRED.value
            ),
            reason=(
                "Private GitHub administration authority is available."
                if state.private_github_admin_authority
                else "Selected route does not require GitHub repository creation."
                if not github_admin_needed
                else "GitHub provider must expose private administration authority."
            ),
            selected_route=route.value,
            next_gate=(
                "GCP_IDENTITY_AND_READBACK"
                if not github_admin_needed or state.private_github_admin_authority
                else "PROVIDER_GITHUB_AUTHORITY"
            ),
        )
    )

    results.append(
        ConstraintResult(
            constraint_id="GITHUB_INSTALLATION_SCOPE",
            state=(
                ResolutionState.RESOLVED.value
                if state.github_installation_scope.lower() == "all"
                else ResolutionState.ELIMINATED_BY_ALTERNATE_ROUTE.value
                if route != ExecutionRoute.PRIVATE_GITHUB_OPS_WIF
                else ResolutionState.PROVIDER_AUTHORITY_REQUIRED.value
            ),
            reason=(
                "GitHub installation has all-repository scope."
                if state.github_installation_scope.lower() == "all"
                else "Selected route does not rely on installation expansion."
                if route != ExecutionRoute.PRIVATE_GITHUB_OPS_WIF
                else "GitHub installation remains selected-repository-only."
            ),
            selected_route=route.value,
            next_gate=(
                "GCP_IDENTITY_AND_READBACK"
                if route != ExecutionRoute.PRIVATE_GITHUB_OPS_WIF
                or state.github_installation_scope.lower() == "all"
                else "EXPAND_INSTALLATION_SCOPE"
            ),
        )
    )

    results.append(
        ConstraintResult(
            constraint_id="GOOGLE_CLOUD_AUTHORITY",
            state=(
                ResolutionState.READY_FOR_FRESH_AUTHORITY.value
                if state.gcp_admin_authority and state.gcp_native_runner_available
                else ResolutionState.PROVIDER_AUTHORITY_REQUIRED.value
            ),
            reason=(
                "Google Cloud administration and a native runner are available."
                if state.gcp_admin_authority and state.gcp_native_runner_available
                else "Google Cloud must expose an authenticated administration runtime."
            ),
            selected_route=route.value,
            next_gate=(
                "METADATA_ONLY_PROVIDER_PROOF"
                if state.gcp_admin_authority and state.gcp_native_runner_available
                else "PROVIDER_GCP_AUTHORITY"
            ),
        )
    )

    results.append(
        ConstraintResult(
            constraint_id="OPENAI_EXISTING_KEY_MANAGEMENT",
            state=(
                ResolutionState.READY_FOR_FRESH_AUTHORITY.value
                if state.openai_existing_key_management_available
                else ResolutionState.PROVIDER_AUTHORITY_REQUIRED.value
            ),
            reason=(
                "Existing-key enumeration and deletion are available."
                if state.openai_existing_key_management_available
                else "Deletion remains an official OpenAI provider-account action."
            ),
            selected_route=route.value,
            next_gate=(
                "DEPENDENCY_MIGRATION_THEN_REVOCATION"
                if state.openai_existing_key_management_available
                else "OFFICIAL_OPENAI_KEY_MANAGEMENT"
            ),
        )
    )

    unresolved = [
        item.constraint_id
        for item in results
        if item.state in {ResolutionState.PROVIDER_AUTHORITY_REQUIRED.value, ResolutionState.BLOCKED.value}
    ]
    internally_closed = [
        item.constraint_id
        for item in results
        if item.state in {ResolutionState.RESOLVED.value, ResolutionState.ELIMINATED_BY_ALTERNATE_ROUTE.value}
    ]
    ready = not unresolved
    payload = {
        "schema": SCHEMA,
        "selected_route": route.value,
        "edge_changes": edges,
        "constraints": [item.to_dict() for item in results],
        "internally_closed": internally_closed,
        "provider_gates": unresolved,
        "admission_state": (
            "READY_FOR_FRESH_OWNER_AUTHORITY"
            if ready
            else "INTERNAL_CONSTRAINTS_CLOSED_PROVIDER_AUTHORITY_REQUIRED"
        ),
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
        "truth_boundary": {
            "alternate_route_grants_provider_authority": False,
            "sealed_artifact_is_a_credential": False,
            "source_or_ci_proves_provider_execution": False,
            "provider_native_readback_required": True,
        },
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def from_mapping(payload: Mapping[str, Any]) -> ProviderState:
    allowed = {field.name for field in ProviderState.__dataclass_fields__.values()}
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise ResolverError(f"unexpected fields: {unexpected}")
    return ProviderState(**payload)


def resolve_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return resolve_constraints(from_mapping(payload))
