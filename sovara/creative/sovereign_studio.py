from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .policy import ContentClass, PrivacyClass


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


def compile_studio_plan(request: StudioRequest) -> StudioPlan:
    """Translate creator intent into a conservative execution-plane plan.

    The planner intentionally does not perform provider calls, deployment,
    publishing, or secret handling. It selects the operational class that the
    orchestration layer should later satisfy with admitted capabilities.
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

    return StudioPlan(
        request_id=request.request_id.strip(),
        primary_plane=primary,
        fallback_planes=fallback,
        requires_rights_gate=mature or request.reference_asset_present,
        requires_private_asset_vault=sensitive or request.reference_asset_present,
        requires_owner_release_approval=True,
        technical_complexity_hidden_from_owner=True,
    )
