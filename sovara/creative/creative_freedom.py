from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ConstraintKind(str, Enum):
    PLATFORM_FORMAT = "PLATFORM_FORMAT"
    MODEL_CAPABILITY = "MODEL_CAPABILITY"
    TOOL_FEATURE = "TOOL_FEATURE"
    QUOTA = "QUOTA"
    LICENSING = "LICENSING"
    POLICY = "POLICY"
    PRIVACY = "PRIVACY"
    DEVICE = "DEVICE"
    COST = "COST"
    LATENCY = "LATENCY"


class ConstraintDisposition(str, Enum):
    ROUTE_AROUND = "ROUTE_AROUND"
    TRANSCODE = "TRANSCODE"
    DECOMPOSE = "DECOMPOSE"
    BUILD_RESIDUAL = "BUILD_RESIDUAL"
    HOLD_EXECUTION = "HOLD_EXECUTION"


@dataclass(frozen=True, slots=True)
class PlatformConstraint:
    source: str
    kind: ConstraintKind
    description: str
    hard_boundary: bool = False


@dataclass(frozen=True, slots=True)
class CreativeIntentContract:
    request_id: str
    objective: str
    required_modalities: tuple[str, ...] = ()
    non_negotiables: tuple[str, ...] = ()
    quality_floor: str = "BEST_AVAILABLE"
    allow_goal_dilution: bool = False


@dataclass(frozen=True, slots=True)
class FreedomRouteAction:
    source: str
    kind: ConstraintKind
    disposition: ConstraintDisposition
    rationale: str


@dataclass(frozen=True, slots=True)
class CreativeFreedomPlan:
    request_id: str
    canonical_objective: str
    objective_preserved: bool
    provider_neutral: bool
    provider_lock_in_allowed: bool
    platform_constraints_may_rewrite_goal: bool
    canonical_intermediate_representation: str
    route_actions: tuple[FreedomRouteAction, ...]
    residual_hard_boundaries: tuple[str, ...]
    execution_held: bool


def _disposition(constraint: PlatformConstraint) -> ConstraintDisposition:
    if constraint.hard_boundary:
        return ConstraintDisposition.HOLD_EXECUTION
    if constraint.kind is ConstraintKind.PLATFORM_FORMAT:
        return ConstraintDisposition.TRANSCODE
    if constraint.kind in {
        ConstraintKind.MODEL_CAPABILITY,
        ConstraintKind.TOOL_FEATURE,
        ConstraintKind.DEVICE,
    }:
        return ConstraintDisposition.ROUTE_AROUND
    if constraint.kind in {
        ConstraintKind.QUOTA,
        ConstraintKind.COST,
        ConstraintKind.LATENCY,
    }:
        return ConstraintDisposition.DECOMPOSE
    if constraint.kind in {
        ConstraintKind.LICENSING,
        ConstraintKind.POLICY,
        ConstraintKind.PRIVACY,
    }:
        return ConstraintDisposition.BUILD_RESIDUAL
    return ConstraintDisposition.ROUTE_AROUND


def compile_creative_freedom_plan(
    intent: CreativeIntentContract,
    constraints: Iterable[PlatformConstraint] = (),
) -> CreativeFreedomPlan:
    """Compile creator intent before any provider/tool choice.

    Provider constraints are execution facts, not permission to rewrite the
    creator's objective. FUSE may route, transcode, decompose, compose or build
    a residual capability. A genuine hard legal/safety/authority boundary holds
    execution while preserving the original design intent unchanged.
    """

    request_id = intent.request_id.strip()
    objective = intent.objective.strip()
    if not request_id:
        raise ValueError("request_id is required")
    if not objective:
        raise ValueError("objective is required")
    if intent.allow_goal_dilution:
        raise ValueError("creative freedom routing forbids goal dilution")

    actions: list[FreedomRouteAction] = []
    residual: list[str] = []

    for constraint in constraints:
        source = constraint.source.strip() or "UNKNOWN_PLATFORM"
        disposition = _disposition(constraint)
        if disposition is ConstraintDisposition.HOLD_EXECUTION:
            residual.append(f"{source}: {constraint.description.strip()}")
            rationale = "hard boundary holds execution without changing creator intent"
        elif disposition is ConstraintDisposition.TRANSCODE:
            rationale = "translate representation instead of reducing the design"
        elif disposition is ConstraintDisposition.DECOMPOSE:
            rationale = "split execution across lawful routes without changing the target result"
        elif disposition is ConstraintDisposition.BUILD_RESIDUAL:
            rationale = "reuse/compose/build the missing capability behind a provider-neutral contract"
        else:
            rationale = "select another capable execution path without changing the target result"

        actions.append(
            FreedomRouteAction(
                source=source,
                kind=constraint.kind,
                disposition=disposition,
                rationale=rationale,
            )
        )

    return CreativeFreedomPlan(
        request_id=request_id,
        canonical_objective=objective,
        objective_preserved=True,
        provider_neutral=True,
        provider_lock_in_allowed=False,
        platform_constraints_may_rewrite_goal=False,
        canonical_intermediate_representation="FUSE_CREATIVE_IR_V1",
        route_actions=tuple(actions),
        residual_hard_boundaries=tuple(residual),
        execution_held=bool(residual),
    )
