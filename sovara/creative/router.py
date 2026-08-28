from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .policy import (
    ContentClass,
    Eligibility,
    MatureContext,
    PrivacyClass,
    RoutePolicy,
    RouteType,
    evaluate_route,
)


_ROUTE_PREFERENCE = {
    RouteType.DETERMINISTIC: 0,
    RouteType.SELF_HOSTED_GCP: 1,
    RouteType.OPENROUTER_FCX: 2,
    RouteType.CREATIVE_TOOL_ADAPTER: 3,
    RouteType.NON_GENERATIVE_DIGITAL: 4,
}


@dataclass(frozen=True, slots=True)
class RouteDecision:
    selected_route_id: str | None
    selected_route_type: str | None
    eligibility: str
    evaluated: tuple[tuple[str, str], ...]
    no_paper_continuity_preserved: bool
    reason: str


def select_route(
    *,
    content_class: ContentClass,
    privacy_class: PrivacyClass,
    candidates: Iterable[RoutePolicy],
    mature_context: MatureContext | None = None,
) -> RouteDecision:
    """Select an eligible route without prompt-obfuscation or policy bypass.

    The function prefers deterministic/sovereign routes before external model
    gateways and guarantees that a non-generative digital route can remain the
    terminal digital fallback when one is supplied and eligible.
    """

    ordered = sorted(candidates, key=lambda route: (_ROUTE_PREFERENCE[route.route_type], route.route_id))
    evaluated: list[tuple[str, str]] = []

    for route in ordered:
        eligibility = evaluate_route(
            content_class=content_class,
            privacy_class=privacy_class,
            route=route,
            mature_context=mature_context,
        )
        evaluated.append((route.route_id, eligibility.value))
        if eligibility in {Eligibility.ELIGIBLE, Eligibility.ELIGIBLE_WITH_RESTRICTIONS}:
            return RouteDecision(
                selected_route_id=route.route_id,
                selected_route_type=route.route_type.value,
                eligibility=eligibility.value,
                evaluated=tuple(evaluated),
                no_paper_continuity_preserved=True,
                reason="eligible_route_selected",
            )

    has_digital_fallback = any(
        route.route_type is RouteType.NON_GENERATIVE_DIGITAL and route.available
        for route in ordered
    )
    return RouteDecision(
        selected_route_id=None,
        selected_route_type=None,
        eligibility=Eligibility.INELIGIBLE.value,
        evaluated=tuple(evaluated),
        no_paper_continuity_preserved=has_digital_fallback,
        reason="no_currently_eligible_route",
    )
