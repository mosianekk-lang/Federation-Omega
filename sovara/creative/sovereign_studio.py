from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .policy import ContentClass, PrivacyClass, RouteType
from .router import RouteDecision


class StudioMode(str, Enum):
    DIRECTOR = "DIRECTOR"
    COLLABORATOR = "COLLABORATOR"
    AUTOPILOT = "AUTOPILOT"


class ExecutionPlane(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    MAINSTREAM_FRONTIER = "MAINSTREAM_FRONTIER"
    PRIVATE_MODEL_CELL = "PRIVATE_MODEL_CELL"
    CREATIVE_TOOL = "CREATIVE_TOOL"
    NON_GENERATIVE_PRIVATE = "NON_GENERATIVE_PRIVATE"


_ROUTE_TO_PLANE = {
    RouteType.DETERMINISTIC.value: ExecutionPlane.DETERMINISTIC,
    RouteType.SELF_HOSTED_GCP.value: ExecutionPlane.PRIVATE_MODEL_CELL,
    RouteType.OPENROUTER_FCX.value: ExecutionPlane.MAINSTREAM_FRONTIER,
    RouteType.CREATIVE_TOOL_ADAPTER.value: ExecutionPlane.CREATIVE_TOOL,
    RouteType.NON_GENERATIVE_DIGITAL.value: ExecutionPlane.NON_GENERATIVE_PRIVATE,
}


@dataclass(frozen=True, slots=True)
class StudioRequest:
    request_id: str
    objective: str
    content_class: ContentClass
    privacy_class: PrivacyClass
    mode: StudioMode = StudioMode.DIRECTOR
    reference_asset_present: bool = False
    provider_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class StudioPlan:
    request_id: str
    primary_plane: ExecutionPlane
    fallback_planes: tuple[ExecutionPlane, ...]
    requires_rights_gate: bool
    requires_private_asset_vault: bool
    requires_owner_release_approval: bool
    technical_complexity_hidden_from_owner: bool
    provider_execution_proven: bool = False
    route_decision_bound: bool = False
    selected_route_id: str | None = None
    selected_route_type: str | None = None


def _plane_from_route_decision(request: StudioRequest, decision: RouteDecision) -> ExecutionPlane:
    if not decision.selected_route_id or not decision.selected_route_type:
        raise ValueError("route_decision must contain one selected eligible route")
    plane = _ROUTE_TO_PLANE.get(decision.selected_route_type)
    if plane is None:
        raise ValueError(f"unsupported canonical route type: {decision.selected_route_type}")

    if request.privacy_class is PrivacyClass.SECRET and plane not in {
        ExecutionPlane.DETERMINISTIC,
        ExecutionPlane.NON_GENERATIVE_PRIVATE,
    }:
        raise ValueError("canonical route decision violates SECRET studio privacy ceiling")
    if request.privacy_class in {PrivacyClass.PRIVATE_ASSET, PrivacyClass.SENSITIVE_PERFORMER} and plane is ExecutionPlane.MAINSTREAM_FRONTIER:
        raise ValueError("canonical route decision violates private studio privacy ceiling")
    return plane


def compile_studio_plan(
    request: StudioRequest,
    *,
    route_decision: RouteDecision | None = None,
) -> StudioPlan:
    """Translate creator intent into a conservative execution-plane plan.

    When a canonical ``RouteDecision`` is supplied, Studio consumes it rather than
    making a second provider/route choice. Fallback selection then remains owned by
    the canonical router: Studio does not invent an independent fallback order.

    Without a route decision, the legacy source-only planning heuristic remains for
    compatibility and design exploration, but the resulting plan explicitly records
    ``route_decision_bound=False`` and cannot be mistaken for a canonical route bind.
    """

    if not request.request_id.strip():
        raise ValueError("request_id is required")
    if not request.objective.strip():
        raise ValueError("objective is required")

    sensitive = request.privacy_class in {
        PrivacyClass.PRIVATE_ASSET,
        PrivacyClass.SENSITIVE_PERFORMER,
        PrivacyClass.SECRET,
    }
    mature = request.content_class is ContentClass.MATURE_ADULT_ORIENTED

    if route_decision is not None:
        primary = _plane_from_route_decision(request, route_decision)
        fallback: tuple[ExecutionPlane, ...] = ()
        selected_route_id = route_decision.selected_route_id
        selected_route_type = route_decision.selected_route_type
        route_bound = True
    else:
        if request.privacy_class is PrivacyClass.SECRET:
            primary = ExecutionPlane.NON_GENERATIVE_PRIVATE
            fallback = (ExecutionPlane.DETERMINISTIC,)
        elif mature or sensitive or request.provider_sensitive:
            primary = ExecutionPlane.PRIVATE_MODEL_CELL
            fallback = (
                ExecutionPlane.NON_GENERATIVE_PRIVATE,
                ExecutionPlane.CREATIVE_TOOL,
            )
        else:
            primary = ExecutionPlane.MAINSTREAM_FRONTIER
            fallback = (
                ExecutionPlane.PRIVATE_MODEL_CELL,
                ExecutionPlane.CREATIVE_TOOL,
                ExecutionPlane.NON_GENERATIVE_PRIVATE,
            )
        selected_route_id = None
        selected_route_type = None
        route_bound = False

    return StudioPlan(
        request_id=request.request_id.strip(),
        primary_plane=primary,
        fallback_planes=fallback,
        requires_rights_gate=mature or request.reference_asset_present,
        requires_private_asset_vault=sensitive or request.reference_asset_present,
        requires_owner_release_approval=True,
        technical_complexity_hidden_from_owner=True,
        route_decision_bound=route_bound,
        selected_route_id=selected_route_id,
        selected_route_type=selected_route_type,
    )
