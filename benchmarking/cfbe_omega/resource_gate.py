from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class SufficiencyState(str, Enum):
    SATISFIED = "SATISFIED"
    REUSE_EXISTING = "REUSE_EXISTING"
    REPURPOSE_EXISTING = "REPURPOSE_EXISTING"
    COMPOSE_EXISTING = "COMPOSE_EXISTING"
    BUILD_REQUIRED = "BUILD_REQUIRED"
    PROVIDER_GATE = "PROVIDER_GATE"
    OWNER_GATE = "OWNER_GATE"
    COST_GATE = "COST_GATE"


@dataclass(frozen=True)
class CapabilityRequirement:
    requirement_id: str
    capability: str
    min_fit: float = 0.80
    provider_live_required: bool = False
    mutation_authority_required: bool = False
    independent_verifier_required: bool = True
    max_incremental_cost: float = 0.0

    def validate(self) -> None:
        if not self.requirement_id or not self.capability:
            raise ValueError("requirement_id and capability are required")
        if not 0 <= self.min_fit <= 1:
            raise ValueError("min_fit must be in [0, 1]")
        if self.max_incremental_cost < 0:
            raise ValueError("max_incremental_cost must be >= 0")


@dataclass(frozen=True)
class CapabilityCandidate:
    candidate_id: str
    capability: str
    fit: float
    evidence_factor: float
    freshness_factor: float = 1.0
    provider_live: bool = False
    mutation_authority: bool = False
    independent_verifier_available: bool = False
    reversible: bool = True
    incremental_cost: float | None = 0.0
    source_kind: str = "INTERNAL"

    def validate(self) -> None:
        if not self.candidate_id or not self.capability:
            raise ValueError("candidate_id and capability are required")
        for name, value in (
            ("fit", self.fit),
            ("evidence_factor", self.evidence_factor),
            ("freshness_factor", self.freshness_factor),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.incremental_cost is not None and self.incremental_cost < 0:
            raise ValueError("incremental_cost must be >= 0 when known")

    @property
    def confidence_fit(self) -> float:
        self.validate()
        return self.fit * self.evidence_factor * self.freshness_factor


@dataclass(frozen=True)
class SufficiencyDecision:
    requirement_id: str
    state: SufficiencyState
    selected_candidate_ids: tuple[str, ...]
    rationale: str
    next_route: str


def _hard_gate(
    requirement: CapabilityRequirement,
    candidate: CapabilityCandidate,
) -> SufficiencyState | None:
    if candidate.incremental_cost is None:
        return SufficiencyState.COST_GATE
    if candidate.incremental_cost > requirement.max_incremental_cost:
        return SufficiencyState.COST_GATE
    if requirement.provider_live_required and not candidate.provider_live:
        return SufficiencyState.PROVIDER_GATE
    if requirement.mutation_authority_required and not candidate.mutation_authority:
        return SufficiencyState.OWNER_GATE
    if requirement.independent_verifier_required and not candidate.independent_verifier_available:
        return SufficiencyState.PROVIDER_GATE
    return None


def evaluate_requirement(
    requirement: CapabilityRequirement,
    candidates: Iterable[CapabilityCandidate],
) -> SufficiencyDecision:
    """Apply REUSE -> EXTEND/REPURPOSE -> COMPOSE -> BUILD ONLY LAST.

    Advisory or simulated systems may be candidates for analysis, design and
    falsification, but they cannot satisfy provider-live requirements unless
    provider execution is independently proven.
    """
    requirement.validate()
    pool = [c for c in candidates if c.capability == requirement.capability]
    for candidate in pool:
        candidate.validate()

    if not pool:
        return SufficiencyDecision(
            requirement.requirement_id,
            SufficiencyState.BUILD_REQUIRED,
            (),
            "No matching capability candidate is currently evidenced.",
            "DISCOVER -> REUSE_COMPONENTS -> BUILD_MINIMUM_MISSING_COMPONENT -> TEST -> CANARY -> READBACK",
        )

    ranked = sorted(pool, key=lambda c: (c.confidence_fit, c.fit), reverse=True)

    for candidate in ranked:
        gate = _hard_gate(requirement, candidate)
        if gate is None and candidate.fit >= requirement.min_fit:
            state = (
                SufficiencyState.SATISFIED
                if candidate.fit >= 0.95
                else SufficiencyState.REUSE_EXISTING
            )
            return SufficiencyDecision(
                requirement.requirement_id,
                state,
                (candidate.candidate_id,),
                f"{candidate.candidate_id} meets fit and all hard gates.",
                "REUSE -> EXECUTE_BOUNDED -> INDEPENDENT_READBACK",
            )

    for candidate in ranked:
        gate = _hard_gate(requirement, candidate)
        if gate is None and candidate.fit >= max(0.60, requirement.min_fit - 0.20):
            return SufficiencyDecision(
                requirement.requirement_id,
                SufficiencyState.REPURPOSE_EXISTING,
                (candidate.candidate_id,),
                f"{candidate.candidate_id} is close enough to adapt rather than rebuild.",
                "EXTEND_OR_ADAPT -> REGRESSION_TEST -> CANARY -> INDEPENDENT_READBACK",
            )

    composable = [
        c for c in ranked if _hard_gate(requirement, c) is None and c.reversible
    ]
    accumulated = 0.0
    selected: list[str] = []
    for candidate in composable:
        accumulated = 1.0 - (1.0 - accumulated) * (1.0 - candidate.fit)
        selected.append(candidate.candidate_id)
        if accumulated >= requirement.min_fit:
            return SufficiencyDecision(
                requirement.requirement_id,
                SufficiencyState.COMPOSE_EXISTING,
                tuple(selected),
                "Multiple reversible capabilities jointly satisfy the functional fit.",
                "COMPOSE_MINIMUM_SET -> INTEGRATION_TEST -> CANARY -> INDEPENDENT_READBACK",
            )

    gates = [_hard_gate(requirement, candidate) for candidate in ranked]
    if SufficiencyState.COST_GATE in gates:
        return SufficiencyDecision(
            requirement.requirement_id,
            SufficiencyState.COST_GATE,
            (ranked[0].candidate_id,),
            "Strongest candidate is blocked by unknown or excessive incremental cost.",
            "FIND_ZERO_COST_EQUIVALENT -> REUSE/REPURPOSE -> OWNER_DECISION_ONLY_IF_IRREDUCIBLE",
        )
    if SufficiencyState.OWNER_GATE in gates:
        return SufficiencyDecision(
            requirement.requirement_id,
            SufficiencyState.OWNER_GATE,
            (ranked[0].candidate_id,),
            "Strongest candidate lacks required mutation authority.",
            "FIND_AUTHORIZED_EQUIVALENT -> STAGE_REVERSIBLE_CHANGE -> OWNER_GATE_IF_IRREDUCIBLE",
        )
    if SufficiencyState.PROVIDER_GATE in gates:
        return SufficiencyDecision(
            requirement.requirement_id,
            SufficiencyState.PROVIDER_GATE,
            (ranked[0].candidate_id,),
            "Strongest candidate lacks provider-live or independent verification proof.",
            "PROVIDER_NATIVE_CANARY_OR_ALTERNATE_VERIFIED_ROUTE",
        )

    return SufficiencyDecision(
        requirement.requirement_id,
        SufficiencyState.BUILD_REQUIRED,
        tuple(candidate.candidate_id for candidate in ranked[:3]),
        "Existing candidates do not meet required fit.",
        "REUSE_COMPONENTS -> BUILD_MINIMUM_MISSING_CAPABILITY -> TEST -> CANARY -> READBACK",
    )


def evaluate_upgrade(
    requirements: Sequence[CapabilityRequirement],
    candidates: Iterable[CapabilityCandidate],
) -> tuple[SufficiencyDecision, ...]:
    pool = tuple(candidates)
    return tuple(evaluate_requirement(req, pool) for req in requirements)


def upgrade_ready(decisions: Sequence[SufficiencyDecision]) -> bool:
    ready_states = {
        SufficiencyState.SATISFIED,
        SufficiencyState.REUSE_EXISTING,
        SufficiencyState.REPURPOSE_EXISTING,
        SufficiencyState.COMPOSE_EXISTING,
    }
    return bool(decisions) and all(decision.state in ready_states for decision in decisions)

