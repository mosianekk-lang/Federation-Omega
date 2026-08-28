from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ContentClass(str, Enum):
    BRAND_COMMERCIAL = "BRAND_COMMERCIAL"
    SOCIAL = "SOCIAL"
    EDITORIAL = "EDITORIAL"
    FASHION_GLAMOUR = "FASHION_GLAMOUR"
    IMAGE = "IMAGE"
    VIDEO_FILM = "VIDEO_FILM"
    AUDIO_MUSIC = "AUDIO_MUSIC"
    VIRTUAL_CREATOR = "VIRTUAL_CREATOR"
    PRESENTATION_VISUAL_STORY = "PRESENTATION_VISUAL_STORY"
    MATURE_ADULT_ORIENTED = "MATURE_ADULT_ORIENTED"


class PrivacyClass(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PRIVATE_ASSET = "PRIVATE_ASSET"
    SENSITIVE_PERFORMER = "SENSITIVE_PERFORMER"
    SECRET = "SECRET"


class RouteType(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    SELF_HOSTED_GCP = "SELF_HOSTED_GCP"
    OPENROUTER_FCX = "OPENROUTER_FCX"
    CREATIVE_TOOL_ADAPTER = "CREATIVE_TOOL_ADAPTER"
    NON_GENERATIVE_DIGITAL = "NON_GENERATIVE_DIGITAL"


class Eligibility(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    ELIGIBLE_WITH_RESTRICTIONS = "ELIGIBLE_WITH_RESTRICTIONS"
    SOVEREIGN_ONLY = "SOVEREIGN_ONLY"
    NON_GENERATIVE_ONLY = "NON_GENERATIVE_ONLY"
    INELIGIBLE = "INELIGIBLE"
    POLICY_RECHECK_REQUIRED = "POLICY_RECHECK_REQUIRED"


_PRIVACY_RANK = {
    PrivacyClass.PUBLIC: 0,
    PrivacyClass.INTERNAL: 1,
    PrivacyClass.PRIVATE_ASSET: 2,
    PrivacyClass.SENSITIVE_PERFORMER: 3,
    PrivacyClass.SECRET: 4,
}


@dataclass(frozen=True, slots=True)
class MatureContext:
    """Minimum eligibility facts for real-person mature/adult-oriented work.

    Values are supplied by a rights/consent provenance system. A model response
    never establishes these facts by itself.
    """

    all_participants_adults: bool
    consent_verified: bool
    ambiguous_age: bool = False
    coercive_or_nonconsensual: bool = False
    hidden_camera_exploitation: bool = False
    nonconsensual_real_person_impersonation: bool = False

    @property
    def hard_gate_passes(self) -> bool:
        return all(
            (
                self.all_participants_adults,
                self.consent_verified,
                not self.ambiguous_age,
                not self.coercive_or_nonconsensual,
                not self.hidden_camera_exploitation,
                not self.nonconsensual_real_person_impersonation,
            )
        )


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    route_id: str
    route_type: RouteType
    privacy_ceiling: PrivacyClass
    policy_verified: bool
    mature_class_allowed: bool = False
    generation_capable: bool = True
    available: bool = True


def evaluate_route(
    *,
    content_class: ContentClass,
    privacy_class: PrivacyClass,
    route: RoutePolicy,
    mature_context: MatureContext | None = None,
) -> Eligibility:
    """Return route eligibility without granting execution authority."""

    if not route.available:
        return Eligibility.INELIGIBLE

    if privacy_class is PrivacyClass.SECRET and route.generation_capable:
        return Eligibility.NON_GENERATIVE_ONLY

    if _PRIVACY_RANK[privacy_class] > _PRIVACY_RANK[route.privacy_ceiling]:
        return Eligibility.INELIGIBLE

    if content_class is ContentClass.MATURE_ADULT_ORIENTED:
        if mature_context is None or not mature_context.hard_gate_passes:
            return Eligibility.INELIGIBLE

        if route.route_type is RouteType.SELF_HOSTED_GCP:
            return Eligibility.ELIGIBLE if route.mature_class_allowed else Eligibility.INELIGIBLE

        if route.route_type is RouteType.NON_GENERATIVE_DIGITAL:
            return Eligibility.ELIGIBLE

        if not route.policy_verified:
            return Eligibility.POLICY_RECHECK_REQUIRED

        return Eligibility.ELIGIBLE if route.mature_class_allowed else Eligibility.INELIGIBLE

    if route.route_type in {RouteType.OPENROUTER_FCX, RouteType.CREATIVE_TOOL_ADAPTER}:
        if not route.policy_verified:
            return Eligibility.POLICY_RECHECK_REQUIRED

    return Eligibility.ELIGIBLE
