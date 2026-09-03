from __future__ import annotations

"""CFBE-selected Bubbles operational closure convergence spine.

This module composes already-existing Federation primitives into one bounded,
machine-readable closure receipt. It deliberately does not create another
scheduler, provider executor, sandbox, capability registry, workspace store,
proof plane, value court, or authority plane.

The spine keeps source/control evidence separate from provider runtime,
provider effects, and owner-value proof.
"""

from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from federation.idea_system_build_runtime import CapabilityRegistryDiscovery, PersistentWorkspace
from federation.sentinel_omega.owner_value_ingress import (
    OwnerValueMissionRecord,
    OwnerValuePairCompiler,
)
from omega_one.interop import OmegaInteropSpine, UniversalCapabilityContract


SCHEMA = "BUBBLES-CFBE-OPERATIONAL-CLOSURE-V1"
_PROVIDER_VERIFIED_STATES = frozenset(
    {
        "VERIFIED",
        "READBACK_VERIFIED",
        "HOSTED_VERIFIED",
        "PROVIDER_LIVE_VERIFIED",
        "AUTHENTICATED_READBACK_VERIFIED",
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value.lower())


def _provider_readback_projection(
    receipts: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    projected: list[dict[str, Any]] = []
    for route_name, raw in sorted(dict(receipts or {}).items()):
        item = dict(raw)
        provider = str(item.get("provider") or route_name).strip()
        state = str(item.get("state") or "UNVERIFIED").strip().upper()
        proof_ref = str(item.get("proof_ref") or "").strip()
        provider_native = item.get("provider_native") is True
        semantic_readback = item.get("semantic_readback") is True
        verified = (
            provider_native
            and semantic_readback
            and bool(proof_ref)
            and state in _PROVIDER_VERIFIED_STATES
        )
        projected.append(
            {
                "route": str(route_name),
                "provider": provider,
                "state": state,
                "provider_native": provider_native,
                "semantic_readback": semantic_readback,
                "proof_ref": proof_ref,
                "verified": verified,
            }
        )
    return {
        "routes": projected,
        "verified_route_count": sum(1 for item in projected if item["verified"]),
        "unverified_route_count": sum(1 for item in projected if not item["verified"]),
        "truth_boundary": {
            "supplied_readback_is_effect_authority": False,
            "one_verified_route_proves_all_provider_routes": False,
            "provider_runtime_inherits_from_source": False,
        },
    }


def _browser_projection(receipt: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(receipt or {})
    verified = (
        item.get("schema") == "BUBBLES-BROWSER-RUNTIME-CANARY-1"
        and item.get("state") == "HOSTED_BROWSER_RUNTIME_VERIFIED"
        and item.get("browser_runtime_verified") is True
        and item.get("javascript_execution_verified") is True
        and item.get("dom_readback_verified") is True
        and item.get("loopback_only") is True
        and item.get("external_network_target_requested") is False
        and item.get("provider_mutation_attempted") is False
        and item.get("secret_values_recorded") is False
        and bool(str(item.get("receipt_sha256") or "").strip())
    )
    return {
        "receipt_supplied": bool(item),
        "hosted_browser_bounded_verified": verified,
        "arbitrary_computer_use_verified": False,
        "external_site_authority_verified": False,
        "provider_mutation_verified": False,
        "receipt_sha256": str(item.get("receipt_sha256") or ""),
        "truth_boundary": (
            "Browser proof is bounded to the exact canary host and loopback semantics; "
            "it never promotes arbitrary computer use, external-site authority, login, or provider effects."
        ),
    }


def _owner_value_projection(
    records: Sequence[OwnerValueMissionRecord],
    *,
    source_head_sha: str,
) -> dict[str, Any]:
    grouped: dict[str, list[OwnerValueMissionRecord]] = {}
    excluded: list[dict[str, str]] = []
    for record in records:
        if record.source_head_sha != source_head_sha:
            excluded.append(
                {
                    "pair_id": record.pair_id,
                    "reason": "SOURCE_HEAD_MISMATCH",
                    "observation_id": record.observation_id,
                }
            )
            continue
        grouped.setdefault(record.pair_id, []).append(record)

    compiled: list[dict[str, Any]] = []
    for pair_id, items in sorted(grouped.items()):
        if len(items) != 2:
            excluded.append({"pair_id": pair_id, "reason": "PAIR_CARDINALITY_NOT_TWO", "observation_id": ""})
            continue
        try:
            pair = OwnerValuePairCompiler.compile(items[0], items[1])
        except ValueError as exc:
            excluded.append({"pair_id": pair_id, "reason": str(exc), "observation_id": ""})
            continue
        compiled.append(pair.to_court_mapping())

    return {
        "eligible_pair_count": len(compiled),
        "existing_value_court_inputs": compiled,
        "excluded": excluded,
        "owner_value_proven": False,
        "stable_promotion_allowed": False,
        "truth_boundary": {
            "pair_eligibility_is_positive_value_proof": False,
            "this_spine_is_a_value_court": False,
            "unmeasured_metrics_are_invented": False,
        },
    }


def compile_operational_closure(
    *,
    mission_id: str,
    trace_id: str,
    source_head_sha: str,
    capability_contract: UniversalCapabilityContract,
    discovery: CapabilityRegistryDiscovery,
    workspace: PersistentWorkspace,
    owner_value_records: Sequence[OwnerValueMissionRecord] = (),
    provider_readbacks: Mapping[str, Mapping[str, Any]] | None = None,
    browser_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile a proof-bound Bubbles operational closure snapshot.

    The function is read-only with respect to external providers. It reads only
    the supplied local registry/workspace/observation inputs and emits a receipt.
    """
    if not str(mission_id).strip():
        raise ValueError("MISSION_ID_REQUIRED")
    if not str(trace_id).strip():
        raise ValueError("TRACE_ID_REQUIRED")
    source_head_sha = str(source_head_sha).lower()
    if not _is_sha(source_head_sha):
        raise ValueError("SOURCE_HEAD_SHA_REQUIRED")

    interop = OmegaInteropSpine.compile(
        capability_contract,
        mission_id=mission_id,
        trace_id=trace_id,
    )
    discovery_snapshot = discovery.snapshot()
    workspace_state = workspace.verify()
    owner_value = _owner_value_projection(
        tuple(owner_value_records),
        source_head_sha=source_head_sha,
    )
    provider_projection = _provider_readback_projection(provider_readbacks)
    browser = _browser_projection(browser_receipt)

    registry_valid = discovery_snapshot.get("registry_state", {}).get("valid") is True
    local_gates = {
        "zero_dilution_interop": interop.zero_dilution_verified is True,
        "capability_registry_integrity": registry_valid,
        "logical_workspace_integrity": workspace_state.get("valid") is True,
        "source_head_bound": True,
    }
    local_core_ready = all(local_gates.values())

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "mission_id": mission_id,
        "trace_id": trace_id,
        "source_head_sha": source_head_sha,
        "state": (
            "SOURCE_CONTROL_CONVERGED_PROVIDER_VALUE_GATED"
            if local_core_ready
            else "SOURCE_CONTROL_INCOMPLETE"
        ),
        "local_gates": local_gates,
        "interop": {
            "capability_id": interop.capability_id,
            "source_ucc_sha256": interop.source_ucc_sha256,
            "zero_dilution_verified": interop.zero_dilution_verified,
            "bundle_sha256": interop.bundle_sha256,
            "mcp_projection_execution_ready": interop.mcp.execution_ready,
            "mcp_projection_hold_reason": interop.mcp.hold_reason,
            "a2a_projection_execution_ready": interop.a2a.execution_ready,
            "a2a_projection_hold_reason": interop.a2a.hold_reason,
            "otel": asdict(interop.otel),
            "otel_provider_export_verified": False,
        },
        "capability_discovery": discovery_snapshot,
        "workspace": {
            **dict(workspace_state),
            "provider_workspace_or_sandbox_verified": False,
        },
        "owner_value": owner_value,
        "provider_readbacks": provider_projection,
        "browser_runtime": browser,
        "ready_for_bounded_provider_evaluation": local_core_ready,
        "provider_effect_authorized": False,
        "stable_promotion_allowed": False,
        "market_superiority_proven": False,
        "truth_boundary": {
            "source_control_convergence_is_provider_runtime": False,
            "otel_projection_is_live_exported_telemetry": False,
            "logical_workspace_is_provider_vm_or_container": False,
            "capability_discovery_is_live_provider_tool_discovery": False,
            "browser_runtime_is_arbitrary_computer_use": False,
            "owner_value_inputs_are_owner_value_proof": False,
            "provider_authority_inherits_from_readback": False,
            "external_effects": 0,
        },
    }
    unsigned = dict(receipt)
    receipt["receipt_sha256"] = _digest(unsigned)
    return receipt


__all__ = [
    "SCHEMA",
    "compile_operational_closure",
]
