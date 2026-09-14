from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence


class EventClass(str, Enum):
    MISSION = "MISSION"
    MAINTENANCE = "MAINTENANCE"
    RECOVERY = "RECOVERY"
    EVOLUTION = "EVOLUTION"


class MaturityState(str, Enum):
    EXISTS = "EXISTS"
    TESTED = "TESTED"
    HOSTED = "HOSTED"
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"
    OPERATIONALLY_OBSERVED = "OPERATIONALLY_OBSERVED"
    VALUE_PROVEN = "VALUE_PROVEN"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    RETIRED = "RETIRED"


class OwnerBoundary(str, Enum):
    NONE = "NONE"
    INTENT = "INTENT"
    AUTHORITY = "AUTHORITY"
    ECONOMIC = "ECONOMIC"
    EXTERNAL_REPRESENTATION = "EXTERNAL_REPRESENTATION"
    DESTRUCTIVE = "DESTRUCTIVE"


@dataclass(frozen=True)
class Objective:
    objective_id: str
    value_weight: float
    urgency_weight: float
    dependencies: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityEvidence:
    capability_id: str
    maturity: MaturityState
    proof_refs: tuple[str, ...] = ()
    owner_burden_minutes: float = 0.0
    cost_units: float = 0.0
    reliability: float = 0.0
    authority_boundary: OwnerBoundary = OwnerBoundary.NONE


@dataclass(frozen=True)
class MaintenanceEvent:
    event_id: str
    event_class: EventClass
    self_resolvable: bool
    reversible: bool
    external_effect: bool = False
    owner_boundary: OwnerBoundary = OwnerBoundary.NONE
    affected_lanes: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterruptionDecision:
    interrupt_owner: bool
    reason: str
    continue_independent_lanes: bool


@dataclass(frozen=True)
class AutonomyDebt:
    owner_continuations: int = 0
    owner_retries: int = 0
    owner_repair_prompts: int = 0
    restated_directives: int = 0
    retriggered_stalls: int = 0
    owner_resolved_internal_drift: int = 0
    repeated_automatable_actions: int = 0
    chat_session_dependencies: int = 0
    unrelated_gate_stalls: int = 0
    rediscovered_failures: int = 0

    @property
    def score(self) -> int:
        return sum(
            (
                self.owner_continuations,
                self.owner_retries,
                self.owner_repair_prompts,
                self.restated_directives,
                self.retriggered_stalls,
                self.owner_resolved_internal_drift,
                self.repeated_automatable_actions,
                self.chat_session_dependencies,
                self.unrelated_gate_stalls,
                self.rediscovered_failures,
            )
        )


@dataclass(frozen=True)
class ObjectiveEcologyResult:
    ranked_objectives: tuple[str, ...]
    shared_unlocks: tuple[tuple[str, int], ...]
    conflicts: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ResourceAllocation:
    objective_id: str
    budget: float
    expected_leverage: float


@dataclass(frozen=True)
class LevelAssessment:
    level: int
    name: str
    qualified: bool
    missing: tuple[str, ...]


OWNER_ONLY_BOUNDARIES = {
    OwnerBoundary.INTENT,
    OwnerBoundary.AUTHORITY,
    OwnerBoundary.ECONOMIC,
    OwnerBoundary.EXTERNAL_REPRESENTATION,
    OwnerBoundary.DESTRUCTIVE,
}


def owner_interruption_firewall(event: MaintenanceEvent) -> InterruptionDecision:
    if event.owner_boundary in OWNER_ONLY_BOUNDARIES:
        return InterruptionDecision(True, f"OWNER_BOUNDARY:{event.owner_boundary.value}", True)
    if event.external_effect:
        return InterruptionDecision(True, "UNSCOPED_EXTERNAL_EFFECT", True)
    if event.self_resolvable and event.reversible:
        return InterruptionDecision(False, "AUTONOMIC_REPAIR", True)
    return InterruptionDecision(False, "DELEGATE_OR_HOLD_LANE", True)


def objective_ecology(objectives: Sequence[Objective]) -> ObjectiveEcologyResult:
    ids = [o.objective_id for o in objectives]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate objective_id")
    known = set(ids)
    for objective in objectives:
        unknown = (set(objective.dependencies) | set(objective.conflicts)) - known
        if unknown:
            raise ValueError(f"unknown objective references: {sorted(unknown)}")

    unlock_counts: dict[str, int] = {}
    for objective in objectives:
        for capability in set(objective.required_capabilities):
            unlock_counts[capability] = unlock_counts.get(capability, 0) + 1

    def priority(o: Objective) -> tuple[float, str]:
        shared = sum(max(0, unlock_counts[c] - 1) for c in set(o.required_capabilities))
        return (o.value_weight * 0.55 + o.urgency_weight * 0.30 + shared * 0.15, o.objective_id)

    ranked = tuple(o.objective_id for o in sorted(objectives, key=priority, reverse=True))
    unlocks = tuple(sorted(unlock_counts.items(), key=lambda item: (-item[1], item[0])))
    conflicts: set[tuple[str, str]] = set()
    for objective in objectives:
        for other in objective.conflicts:
            conflicts.add(tuple(sorted((objective.objective_id, other))))
    return ObjectiveEcologyResult(ranked, unlocks, tuple(sorted(conflicts)))


def allocate_resources(
    objectives: Sequence[Objective],
    total_budget: float,
    *,
    minimum_slice: float = 0.0,
) -> tuple[ResourceAllocation, ...]:
    if total_budget < 0 or minimum_slice < 0:
        raise ValueError("budget must be non-negative")
    if not objectives:
        return ()
    ecology = objective_ecology(objectives)
    by_id = {o.objective_id: o for o in objectives}
    weights: dict[str, float] = {}
    for rank, objective_id in enumerate(ecology.ranked_objectives, start=1):
        objective = by_id[objective_id]
        weights[objective_id] = max(0.0, objective.value_weight + objective.urgency_weight + (len(objectives) - rank + 1) / len(objectives))
    total_weight = sum(weights.values()) or float(len(objectives))
    remaining = max(0.0, total_budget - minimum_slice * len(objectives))
    allocations = []
    for objective_id in ecology.ranked_objectives:
        budget = minimum_slice + remaining * (weights[objective_id] / total_weight)
        allocations.append(ResourceAllocation(objective_id, round(budget, 6), round(weights[objective_id], 6)))
    return tuple(allocations)


def architecture_entropy_recommendation(
    capability_to_responsibilities: Mapping[str, Iterable[str]],
    *,
    overlap_threshold: float = 0.8,
) -> tuple[tuple[str, str, float], ...]:
    if not 0 < overlap_threshold <= 1:
        raise ValueError("overlap_threshold must be within (0, 1]")
    normalized = {k: set(v) for k, v in capability_to_responsibilities.items()}
    keys = sorted(normalized)
    recommendations: list[tuple[str, str, float]] = []
    for index, left in enumerate(keys):
        for right in keys[index + 1 :]:
            union = normalized[left] | normalized[right]
            if not union:
                continue
            score = len(normalized[left] & normalized[right]) / len(union)
            if score >= overlap_threshold:
                recommendations.append((left, right, round(score, 6)))
    return tuple(recommendations)


def owner_attention_leverage(verified_value_units: float, owner_minutes: float) -> float:
    if verified_value_units < 0 or owner_minutes < 0:
        raise ValueError("inputs must be non-negative")
    return round(verified_value_units / max(owner_minutes, 1.0), 6)


def assess_levels(signals: Mapping[str, bool]) -> tuple[LevelAssessment, ...]:
    requirements = {
        5: (
            "objective_ecology",
            "resource_economy",
            "owner_interruption_firewall",
            "autonomy_debt",
            "dynamic_topology",
            "digital_twin",
        ),
        6: (
            "measured_gap_evolution",
            "historical_replay",
            "adversarial_qualification",
            "architectural_entropy_controller",
            "causal_learning",
            "no_self_authority_promotion",
        ),
        7: (
            "persistent_no_chat_continuity",
            "unified_autonomic_loops",
            "irreducible_owner_interruptions_only",
            "verified_value_retention",
            "lane_local_failure_isolation",
            "dynamic_reorganization",
        ),
        8: (
            "multi_timescale_objective_optimization",
            "constitutional_amendment_court",
            "capability_market",
            "cross_provider_counterfactuals",
            "information_value_budgeting",
            "negative_knowledge_diffusion",
        ),
    }
    names = {
        5: "INSTITUTIONAL_INTELLIGENCE",
        6: "SELF_EVOLVING_INSTITUTION",
        7: "SOVEREIGN_DIGITAL_ORGANIZATION",
        8: "EVIDENCE_GOVERNED_ADAPTIVE_INSTITUTION",
    }
    assessments = []
    lower_qualified = True
    for level in sorted(requirements):
        missing = tuple(key for key in requirements[level] if not bool(signals.get(key, False)))
        qualified = lower_qualified and not missing
        assessments.append(LevelAssessment(level, names[level], qualified, missing))
        lower_qualified = qualified
    return tuple(assessments)


def institutional_receipt(*, source_sha: str, payload: Mapping[str, object]) -> str:
    body = {"source_sha": source_sha, "payload": payload, "external_effect": False, "authority_inherited": False}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()
