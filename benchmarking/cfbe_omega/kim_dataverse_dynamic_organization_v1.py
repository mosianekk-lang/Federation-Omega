from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class OrganizationPattern(str, Enum):
    SOLO_SPECIALIST = "SOLO_SPECIALIST"
    BUILDER_FALSIFIER_WITNESS = "BUILDER_FALSIFIER_WITNESS"
    RESEARCH_CELL = "RESEARCH_CELL"
    INCIDENT_RESPONSE_CELL = "INCIDENT_RESPONSE_CELL"
    SCIENTIFIC_TOURNAMENT = "SCIENTIFIC_TOURNAMENT"
    PROVIDER_RECOVERY_SWARM = "PROVIDER_RECOVERY_SWARM"
    ARCHITECTURE_COUNCIL = "ARCHITECTURE_COUNCIL"


@dataclass(frozen=True)
class OrganizationContext:
    task_complexity: float
    uncertainty: float
    consequence: float
    failure_active: bool
    provider_failure: bool
    architecture_change: bool
    independent_witness_required: bool
    parallel_safe_work_items: int


@dataclass(frozen=True)
class OrganizationPlan:
    pattern: OrganizationPattern
    roles: tuple[str, ...]
    max_parallelism: int
    permanent_agents_created: int
    external_effect_authorized: bool


def compile_dynamic_organization(context: OrganizationContext) -> OrganizationPlan:
    for value in (context.task_complexity, context.uncertainty, context.consequence):
        if not 0.0 <= value <= 1.0:
            raise ValueError("bounded context values must be within [0,1]")
    if context.parallel_safe_work_items < 0:
        raise ValueError("parallel_safe_work_items must be non-negative")

    if context.provider_failure:
        pattern = OrganizationPattern.PROVIDER_RECOVERY_SWARM
        roles = ("provider-diagnostician", "route-challenger", "semantic-witness")
    elif context.failure_active:
        pattern = OrganizationPattern.INCIDENT_RESPONSE_CELL
        roles = ("diagnostician", "repair-builder", "regression-witness")
    elif context.architecture_change:
        pattern = OrganizationPattern.ARCHITECTURE_COUNCIL
        roles = ("architect", "entropy-critic", "falsifier", "proof-witness")
    elif context.uncertainty >= 0.7:
        pattern = OrganizationPattern.SCIENTIFIC_TOURNAMENT
        roles = ("champion", "challenger", "scientist", "falsifier", "witness")
    elif context.task_complexity >= 0.6:
        pattern = OrganizationPattern.BUILDER_FALSIFIER_WITNESS
        roles = ("builder", "falsifier", "witness")
    elif context.parallel_safe_work_items >= 3:
        pattern = OrganizationPattern.RESEARCH_CELL
        roles = ("researcher", "researcher", "synthesizer")
    else:
        pattern = OrganizationPattern.SOLO_SPECIALIST
        roles = ("specialist",)

    if context.independent_witness_required and "witness" not in " ".join(roles):
        roles = roles + ("independent-witness",)
    max_parallelism = max(1, min(context.parallel_safe_work_items or 1, len(roles)))
    if context.consequence >= 0.8:
        max_parallelism = min(max_parallelism, 2)
    return OrganizationPlan(pattern, roles, max_parallelism, 0, False)


def organization_dissolves_after_mission(plan: OrganizationPlan) -> bool:
    return plan.permanent_agents_created == 0
