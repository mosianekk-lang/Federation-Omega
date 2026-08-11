from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from federation_consolidation.provider_constraint_resolver import resolve_payload


SCHEMA = "AO-COMMERCIAL-EXECUTION-PLANE-ADMISSION-1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class CommercialExecutionPlaneError(RuntimeError):
    """Fail-closed commercial execution-plane admission error."""


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _require_hash(value: str, pattern: re.Pattern[str], name: str) -> None:
    if not pattern.fullmatch(value):
        raise CommercialExecutionPlaneError(f"{name} is invalid")


def _verify_embedded_hash(payload: Mapping[str, Any], field: str) -> str:
    claimed = str(payload.get(field, ""))
    _require_hash(claimed, HEX64, field)
    body = dict(payload)
    body.pop(field, None)
    calculated = canonical_sha256(body)
    if claimed != calculated:
        raise CommercialExecutionPlaneError(f"{field} verification failed")
    return claimed


def _validate_commercial_truth(truth: Mapping[str, Any]) -> None:
    required = {
        "customer_demand": "MARKET_PROOF_REQUIRED",
        "signed_customer_contract": "NOT_PROVEN",
        "payment_provider_operation": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
        "cloud_run_operation": "NOT_PROVEN",
        "enterprise_assurance": "UNVERIFIED",
        "partner_adoption": "MARKET_PROOF_REQUIRED",
        "production_scale": "PRODUCTION_PROOF_REQUIRED",
        "verified_live_revenue_events": 0,
        "full_commercial_maturity": False,
        "self_service_saas": "HELD",
        "service_enabled_platform": "VERIFIED_AND_PRIORISED",
    }
    for field, expected in required.items():
        if truth.get(field) != expected:
            raise CommercialExecutionPlaneError(
                f"commercial truth boundary changed for {field}"
            )


def build_execution_plane_admission(
    *,
    provider_state: Mapping[str, Any],
    predecessor_checkpoint: Mapping[str, Any],
    predecessor_projection: Mapping[str, Any],
    commercial_truth: Mapping[str, Any],
    provider_readback: Mapping[str, Any],
    source_sha: str,
    phoenix_artifact_digest: str,
) -> dict[str, Any]:
    """Build a hash-bound, no-effect commercial execution-plane admission receipt.

    The receipt may eliminate avoidable private-GitHub dependencies and identify
    route-specific authority gates. It never grants provider authority, consumes
    owner authorization, mutates a provider, or advances an external commercial
    maturity gate.
    """

    _require_hash(source_sha, HEX40, "source_sha")
    digest = phoenix_artifact_digest.removeprefix("sha256:")
    _require_hash(digest, HEX64, "phoenix_artifact_digest")
    predecessor_checkpoint_sha = _verify_embedded_hash(
        predecessor_checkpoint, "checkpoint_sha256"
    )
    predecessor_projection_sha = _verify_embedded_hash(
        predecessor_projection, "projection_sha256"
    )
    _validate_commercial_truth(commercial_truth)

    if provider_readback.get("provider_mutation_performed") is not False:
        raise CommercialExecutionPlaneError("provider readback is not read-only")
    if provider_readback.get("installed_repositories") != [
        "mosianekk-lang/Federation-Omega"
    ]:
        raise CommercialExecutionPlaneError(
            "fresh GitHub installation readback changed"
        )
    if provider_readback.get("target_core_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise CommercialExecutionPlaneError("Core repository truth boundary changed")
    if provider_readback.get("target_ops_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise CommercialExecutionPlaneError("Ops repository truth boundary changed")

    state = dict(provider_state)
    if state.get("live_main") != source_sha:
        raise CommercialExecutionPlaneError("provider state is not bound to source_sha")
    if state.get("phoenix_artifact_sha256") != digest:
        raise CommercialExecutionPlaneError(
            "provider state is not bound to the Phoenix artifact"
        )

    resolution = resolve_payload(state)
    if resolution.get("provider_mutation_performed") is not False:
        raise CommercialExecutionPlaneError("constraint resolver mutated a provider")
    if resolution.get("credential_value_recorded") is not False:
        raise CommercialExecutionPlaneError("constraint resolver recorded credentials")

    constraints = {
        item["constraint_id"]: item for item in resolution["constraints"]
    }
    route = resolution["selected_route"]
    route_specific_gates: list[str] = []

    drift = constraints["LIVE_MAIN_OR_ARTIFACT_DRIFT"]["state"]
    if drift != "RESOLVED":
        route_specific_gates.append("REGENERATE_JUST_IN_TIME_CANDIDATE")

    if route == "PRIVATE_GITHUB_OPS_WIF":
        for constraint_id in (
            "PRIVATE_CORE_OPS_VISIBILITY",
            "PRIVATE_GITHUB_ADMIN_AUTHORITY",
            "GITHUB_INSTALLATION_SCOPE",
            "GOOGLE_CLOUD_AUTHORITY",
        ):
            if constraints[constraint_id]["state"] not in {
                "RESOLVED",
                "READY_FOR_FRESH_AUTHORITY",
            }:
                route_specific_gates.append(constraint_id)
    elif route == "GCP_NATIVE_SEALED_ARTIFACT":
        if constraints["GOOGLE_CLOUD_AUTHORITY"]["state"] != "READY_FOR_FRESH_AUTHORITY":
            route_specific_gates.append("GOOGLE_CLOUD_AUTHORITY")
    elif route == "OWNER_ONLY_SEALED_PACKET":
        route_specific_gates.append(
            "OWNER_RESERVED_EXTERNAL_EXECUTION_AUTHORITY_AND_PROVIDER_NATIVE_READBACK"
        )
    else:
        route_specific_gates.append(
            "SEALED_OWNER_PACKET_OR_GCP_NATIVE_RUNNER_AND_AUTHORITY"
        )

    status = (
        "READY_FOR_FRESH_EXACT_OWNER_AUTHORIZATION"
        if not route_specific_gates
        else "PROVIDER_BLOCKED_ROUTE_SPECIFIC_AUTHORITY_OR_PACKET_REQUIRED"
    )
    result = {
        "schema": SCHEMA,
        "status": status,
        "source_sha": source_sha,
        "phoenix_artifact_sha256": digest,
        "predecessor_checkpoint_sha256": predecessor_checkpoint_sha,
        "predecessor_projection_sha256": predecessor_projection_sha,
        "selected_route": route,
        "constraint_resolution_sha256": resolution["receipt_sha256"],
        "internally_closed_constraints": resolution["internally_closed"],
        "route_specific_gates": sorted(set(route_specific_gates)),
        "independent_open_gate": {
            "openai_existing_key_management": constraints[
                "OPENAI_EXISTING_KEY_MANAGEMENT"
            ]["state"],
            "blocks_execution_plane_selection": False,
        },
        "provider_readback": dict(provider_readback),
        "commercial_truth": dict(commercial_truth),
        "owner_authority": {
            "financial_commitments": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "external_communications": "OWNER_RESERVED",
            "consequential_releases": "OWNER_RESERVED",
            "execution_plane_cutover": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED",
        },
        "provider_mutation_performed": False,
        "external_effect_performed": False,
        "owner_authorization_consumed": False,
        "external_commercial_gate_advanced": False,
        "truth_boundary": {
            "alternate_route_grants_provider_authority": False,
            "sealed_packet_proves_cloud_run": False,
            "source_or_ci_proves_customer_demand": False,
            "provider_native_readback_required": True,
        },
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result
