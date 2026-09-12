from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ProviderScenario:
    provider_id: str
    available: bool
    semantic_fit: float
    reliability: float
    cost: float
    latency: float
    provider_verified: bool


@dataclass(frozen=True)
class CounterfactualRoute:
    provider_id: str
    utility: float
    provider_live_claim: bool


def rank_provider_counterfactuals(scenarios: Sequence[ProviderScenario]) -> tuple[CounterfactualRoute, ...]:
    ids = [item.provider_id for item in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate provider_id")
    routes = []
    for item in scenarios:
        if not 0.0 <= item.semantic_fit <= 1.0 or not 0.0 <= item.reliability <= 1.0:
            raise ValueError("fit and reliability must be within [0,1]")
        if item.cost < 0 or item.latency < 0:
            raise ValueError("cost and latency must be non-negative")
        if not item.available:
            continue
        utility = item.semantic_fit * 0.45 + item.reliability * 0.35 - min(item.cost / 100.0, 1.0) * 0.1 - min(item.latency / 10000.0, 1.0) * 0.1
        routes.append(CounterfactualRoute(item.provider_id, round(utility, 6), item.provider_verified))
    return tuple(sorted(routes, key=lambda item: (-item.utility, item.provider_id)))


def provider_loss_resilience(scenarios: Sequence[ProviderScenario]) -> bool:
    eligible = rank_provider_counterfactuals(scenarios)
    return len(eligible) >= 2
