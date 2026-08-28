from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .policy import ContentClass, PrivacyClass


class RightsState(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CreativeMissionGenome:
    mission_id: str
    content_class: ContentClass
    objective: str
    privacy_class: PrivacyClass
    required_modalities: tuple[str, ...] = field(default_factory=tuple)
    target_channels: tuple[str, ...] = field(default_factory=tuple)
    rights_state: RightsState = RightsState.PENDING
    owner_approval_required: bool = False

    @classmethod
    def build(
        cls,
        *,
        mission_id: str,
        content_class: ContentClass,
        objective: str,
        privacy_class: PrivacyClass,
        required_modalities: Iterable[str] = (),
        target_channels: Iterable[str] = (),
        rights_state: RightsState = RightsState.PENDING,
        owner_approval_required: bool = False,
    ) -> "CreativeMissionGenome":
        mission_id = mission_id.strip()
        objective = objective.strip()
        if not mission_id:
            raise ValueError("mission_id is required")
        if not objective:
            raise ValueError("objective is required")

        modalities = tuple(sorted({m.strip().lower() for m in required_modalities if m.strip()}))
        channels = tuple(sorted({c.strip().lower() for c in target_channels if c.strip()}))

        if content_class is ContentClass.MATURE_ADULT_ORIENTED and rights_state is not RightsState.VERIFIED:
            raise ValueError("mature/adult-oriented real-person mission requires VERIFIED rights state")

        return cls(
            mission_id=mission_id,
            content_class=content_class,
            objective=objective,
            privacy_class=privacy_class,
            required_modalities=modalities,
            target_channels=channels,
            rights_state=rights_state,
            owner_approval_required=owner_approval_required,
        )
