from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


class SurfaceState(str, Enum):
    CONNECTED_READ_WRITE = "CONNECTED_READ_WRITE"
    CONNECTED_READ = "CONNECTED_READ"
    RUNTIME_ADAPTER_AVAILABLE = "RUNTIME_ADAPTER_AVAILABLE"
    SUBSCRIPTION_KNOWN = "SUBSCRIPTION_KNOWN"
    DISCOVERED_UNVERIFIED = "DISCOVERED_UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"


VERIFIED_STATES = {
    SurfaceState.CONNECTED_READ_WRITE,
    SurfaceState.CONNECTED_READ,
    SurfaceState.RUNTIME_ADAPTER_AVAILABLE,
}


@dataclass(frozen=True)
class Capability:
    capability_id: str
    roles: frozenset[str]
    state: SurfaceState
    reliability: float = 1.0
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False


@dataclass(frozen=True)
class CapabilityPlan:
    selected: tuple[str, ...]
    covered_roles: tuple[str, ...]
    unresolved_roles: tuple[str, ...]
    ao_cra_builds: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False


def select_minimum_sufficient_capabilities(
    required_roles: Iterable[str],
    capabilities: Sequence[Capability],
) -> CapabilityPlan:
    """Greedy, fail-closed capability composition for Federation Omega.

    Only currently verified/adapter-backed capabilities are eligible. Missing
    roles become AO-CRA engineering builds rather than invented capability.
    """
    uncovered = set(required_roles)
    selected: list[str] = []
    eligible = [
        item
        for item in capabilities
        if item.state in VERIFIED_STATES
        and item.authority_ceiling in {"A0_READ_ONLY", "A1_INTERNAL"}
    ]

    while uncovered:
        best: Capability | None = None
        best_cover: set[str] = set()
        best_score = -1.0
        for capability in eligible:
            if capability.capability_id in selected:
                continue
            cover = uncovered & set(capability.roles)
            score = len(cover) * max(0.0, min(1.0, capability.reliability))
            if cover and score > best_score:
                best = capability
                best_cover = cover
                best_score = score
        if best is None:
            break
        selected.append(best.capability_id)
        uncovered -= best_cover

    covered = set(required_roles) - uncovered
    builds = tuple(sorted(f"AO-CRA:{role}" for role in uncovered))
    return CapabilityPlan(
        selected=tuple(selected),
        covered_roles=tuple(sorted(covered)),
        unresolved_roles=tuple(sorted(uncovered)),
        ao_cra_builds=builds,
    )


def build_innovation_frontier(
    *,
    strongest_verified_reuse: str,
    strongest_incremental_improvement: str,
    strongest_materially_different_solution: str,
    highest_information_reversible_experiment: str,
) -> Mapping[str, object]:
    frontier = {
        "verified_reuse": strongest_verified_reuse.strip(),
        "incremental_improvement": strongest_incremental_improvement.strip(),
        "materially_different_solution": strongest_materially_different_solution.strip(),
        "reversible_experiment": highest_information_reversible_experiment.strip(),
    }
    missing = [key for key, value in frontier.items() if not value]
    if missing:
        raise ValueError("incomplete Federation innovation frontier: " + ",".join(missing))
    return {
        **frontier,
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
    }


SOURCE_PRECEDENCE = (
    "CURRENT_PROVIDER_NATIVE_READBACK",
    "CURRENT_OFFICIAL_PRIMARY_LEGAL_AUTHORITY",
    "AUTHENTICATED_NATIVE_EVIDENCE",
    "VERIFIED_PROVIDER_EXPORT",
    "VERIFIED_KDV_CANONICAL_CONTROL",
    "VERIFIED_INDEPENDENT_SECONDARY_SOURCE",
    "DERIVATIVE_ANALYSIS",
    "USER_SUPPLIED_ASSERTION",
    "MODEL_OUTPUT",
    "INFERENCE",
    "HYPOTHESIS",
)
