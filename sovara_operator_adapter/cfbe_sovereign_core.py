#!/usr/bin/env python3
"""CFBE-Ω sovereign, provider-neutral routing and verification core.

This module intentionally contains no ChatGPT, OpenAI, Gemini, Google, Microsoft,
or vendor SDK dependency. Platforms are execution/advisory adapters; they are not
CFBE authority roots. Durable state and provider truth remain external to this
pure decision core and are supplied as evidence-bound inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import hashlib
import json
from typing import Any, Iterable, Mapping, Sequence

CORE_CONTRACT = "CFBE_OMEGA_SOVEREIGN_CORE_V2"
CORE_VERSION = "2.0.0"


class SovereignCoreError(ValueError):
    """Raised when an input violates a CFBE sovereignty invariant."""


class Authority(IntEnum):
    A0_READ = 0
    A1_INTERNAL = 1
    PROVIDER_ACTION = 2
    CONSEQUENTIAL = 3


_SECRET_MARKERS = {
    "api_key",
    "apikey",
    "password",
    "passwd",
    "private_key",
    "secret_value",
    "access_token",
    "refresh_token",
    "bearer_token",
}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _assert_secret_safe(value: Any, path: str = "$") -> None:
    """Reject raw credential-shaped payloads from the sovereign core state."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SECRET_MARKERS:
                raise SovereignCoreError(f"raw secret-shaped field prohibited at {path}.{key}")
            _assert_secret_safe(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_secret_safe(child, f"{path}[{index}]")


@dataclass(frozen=True)
class AdapterCapability:
    """Evidence-bound snapshot of one execution/advisory surface."""

    adapter_id: str
    surface_class: str
    capabilities: frozenset[str]
    authority_ceiling: Authority
    presence_state: str
    provider_execution_state: str
    freshness_state: str = "CURRENT"
    cost_class: str = "INCLUDED"
    reversible: bool = True
    semantic_readback: bool = False
    proof_ref: str = ""
    truth_boundary: str = ""

    def __post_init__(self) -> None:
        if not self.adapter_id or not self.surface_class:
            raise SovereignCoreError("adapter identity and surface class are required")
        if not self.capabilities:
            raise SovereignCoreError(f"adapter {self.adapter_id} requires capabilities")
        if self.cost_class not in {"INCLUDED", "ZERO", "UNKNOWN", "PAID"}:
            raise SovereignCoreError(f"unsupported cost class for {self.adapter_id}")

    @property
    def is_current(self) -> bool:
        return self.freshness_state in {"CURRENT", "FRESH"}

    @property
    def is_present(self) -> bool:
        return self.presence_state in {
            "CONNECTED",
            "CONNECTED_VERIFIED",
            "PRESENT_VERIFIED",
            "ACTIVE",
            "OPERATIONAL_SCOPED",
        }

    @property
    def provider_live(self) -> bool:
        return self.provider_execution_state in {
            "PROVIDER_LIVE",
            "PROVIDER_VERIFIED",
            "PROVIDER_VERIFIED_SCOPED",
            "CI_AND_SOURCE_LIVE",
            "OPERATIONAL_SCOPED",
        }


@dataclass(frozen=True)
class MissionRequirement:
    objective_id: str
    capability: str
    authority_required: Authority = Authority.A0_READ
    provider_execution_required: bool = False
    independent_verifier_required: bool = False
    reversible_required: bool = False
    included_cost_only: bool = True
    excluded_surface_classes: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.objective_id or not self.capability:
            raise SovereignCoreError("objective_id and capability are required")


@dataclass(frozen=True)
class RouteCandidate:
    adapter_id: str
    surface_class: str
    rank_score: int
    proof_ref: str
    truth_boundary: str


@dataclass(frozen=True)
class VerificationReceipt:
    action_id: str
    action_fingerprint: str
    executor_adapter_id: str
    verifier_adapter_id: str
    semantic_readback: bool
    result_state: str
    proof_ref: str

    def verify(self) -> bool:
        if self.executor_adapter_id == self.verifier_adapter_id:
            return False
        if not self.semantic_readback:
            return False
        return self.result_state in {"PASS", "VERIFIED", "RECOVERED"} and bool(self.proof_ref)


@dataclass(frozen=True)
class CFBEEvent:
    event_id: str
    event_type: str
    source_adapter_id: str
    payload: Mapping[str, Any]
    proof_ref: str

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_type or not self.source_adapter_id:
            raise SovereignCoreError("event identity/type/source are required")
        _assert_secret_safe(self.payload)

    @property
    def fingerprint(self) -> str:
        return canonical_sha256(
            {
                "contract": CORE_CONTRACT,
                "event_id": self.event_id,
                "event_type": self.event_type,
                "source_adapter_id": self.source_adapter_id,
                "payload": self.payload,
                "proof_ref": self.proof_ref,
            }
        )


def _eligible(adapter: AdapterCapability, mission: MissionRequirement) -> bool:
    if adapter.surface_class in mission.excluded_surface_classes:
        return False
    if not adapter.is_current or not adapter.is_present:
        return False
    if mission.capability not in adapter.capabilities:
        return False
    if adapter.authority_ceiling < mission.authority_required:
        return False
    if mission.provider_execution_required and not adapter.provider_live:
        return False
    if mission.reversible_required and not adapter.reversible:
        return False
    if mission.included_cost_only and adapter.cost_class not in {"INCLUDED", "ZERO"}:
        return False
    return True


def rank_routes(
    mission: MissionRequirement, adapters: Iterable[AdapterCapability]
) -> tuple[RouteCandidate, ...]:
    """Return deterministic provider-neutral routes without authority inheritance."""
    candidates: list[RouteCandidate] = []
    for adapter in adapters:
        if not _eligible(adapter, mission):
            continue
        score = 0
        score += 40 if adapter.provider_live else 0
        score += 25 if adapter.semantic_readback else 0
        score += 15 if adapter.cost_class in {"ZERO", "INCLUDED"} else 0
        score += 10 if adapter.reversible else 0
        score += min(int(adapter.authority_ceiling), int(mission.authority_required)) * 5
        candidates.append(
            RouteCandidate(
                adapter_id=adapter.adapter_id,
                surface_class=adapter.surface_class,
                rank_score=score,
                proof_ref=adapter.proof_ref,
                truth_boundary=adapter.truth_boundary,
            )
        )
    return tuple(sorted(candidates, key=lambda item: (-item.rank_score, item.adapter_id)))


def select_route(
    mission: MissionRequirement, adapters: Iterable[AdapterCapability]
) -> RouteCandidate:
    routes = rank_routes(mission, adapters)
    if not routes:
        raise SovereignCoreError(
            f"no admissible route for objective={mission.objective_id} capability={mission.capability}"
        )
    return routes[0]


def failover_route(
    mission: MissionRequirement,
    adapters: Iterable[AdapterCapability],
    failed_adapter_ids: Iterable[str],
) -> RouteCandidate:
    failed = frozenset(failed_adapter_ids)
    routes = tuple(route for route in rank_routes(mission, adapters) if route.adapter_id not in failed)
    if not routes:
        raise SovereignCoreError("authorised route-space exhausted after failover exclusions")
    return routes[0]


def require_independent_verification(
    receipt: VerificationReceipt, *, expected_action_fingerprint: str
) -> None:
    if receipt.action_fingerprint != expected_action_fingerprint:
        raise SovereignCoreError("verification receipt action fingerprint mismatch")
    if not receipt.verify():
        raise SovereignCoreError("material action lacks independent semantic verification")


def platform_independence_state(
    adapters: Sequence[AdapterCapability],
    execution_proof_adapter_ids: Iterable[str] = (),
    failover_semantic_proof: bool = False,
) -> str:
    """Classify proven independence without confusing design with operation."""
    by_id = {adapter.adapter_id: adapter for adapter in adapters}
    proven = [by_id[item] for item in execution_proof_adapter_ids if item in by_id]
    proven_classes = {item.surface_class for item in proven}
    non_chatgpt = {item for item in proven_classes if item != "CHATGPT"}
    if len(proven_classes) >= 2 and non_chatgpt and failover_semantic_proof:
        return "SURFACE_INDEPENDENT_OPERATIONAL"
    if len(proven_classes) >= 2 and non_chatgpt:
        return "MULTI_SURFACE_EXECUTION_PROVEN"
    if non_chatgpt:
        return "CORE_PORTABLE_NON_CHATGPT_PROVEN"
    return "CONTROL_PLANE_NEUTRAL"


def portable_state_projection(
    *,
    state: Mapping[str, Any],
    adapters: Sequence[AdapterCapability],
    execution_proof_adapter_ids: Iterable[str] = (),
    failover_semantic_proof: bool = False,
) -> dict[str, Any]:
    """Build a deterministic state projection that contains no host-platform authority."""
    _assert_secret_safe(state)
    normalized_adapters = [
        {
            "adapter_id": item.adapter_id,
            "surface_class": item.surface_class,
            "capabilities": sorted(item.capabilities),
            "authority_ceiling": int(item.authority_ceiling),
            "presence_state": item.presence_state,
            "provider_execution_state": item.provider_execution_state,
            "freshness_state": item.freshness_state,
            "cost_class": item.cost_class,
            "reversible": item.reversible,
            "semantic_readback": item.semantic_readback,
            "proof_ref": item.proof_ref,
            "truth_boundary": item.truth_boundary,
        }
        for item in sorted(adapters, key=lambda value: value.adapter_id)
    ]
    projection = {
        "contract": CORE_CONTRACT,
        "version": CORE_VERSION,
        "platform_independence_state": platform_independence_state(
            adapters,
            execution_proof_adapter_ids=execution_proof_adapter_ids,
            failover_semantic_proof=failover_semantic_proof,
        ),
        "state": dict(state),
        "adapters": normalized_adapters,
    }
    projection["state_fingerprint"] = canonical_sha256(projection)
    return projection
