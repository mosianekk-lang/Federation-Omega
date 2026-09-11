from __future__ import annotations

from dataclasses import dataclass
from math import log, sqrt
from typing import Dict, Iterable, Optional, Tuple

from .kernel import CapabilityProfile
from .planner import (
    GlobalCapabilityCompiler,
    PlannedRoute,
    RoutePolicy,
    RoutePreferences,
)


def route_signature(route: PlannedRoute) -> Tuple[Tuple[str, str], ...]:
    return tuple(
        sorted(
            (cap_id, meta.implementation.impl_id)
            for cap_id, meta in route.selected.items()
        )
    )


@dataclass(frozen=True)
class RouteOutcome:
    task_class: str
    signature: Tuple[Tuple[str, str], ...]
    success: bool
    quality: float
    cost_units: float
    latency_ms: float
    owner_intervention_minutes: float = 0.0

    @property
    def reward(self) -> float:
        """Normalized owner-value proxy used only for challenger prioritization."""
        return (
            (1.0 if self.success else -1.0)
            + max(0.0, min(1.0, self.quality))
            - 0.20 * max(0.0, self.cost_units)
            - 0.10 * max(0.0, self.latency_ms) / 10000.0
            - 0.10 * max(0.0, self.owner_intervention_minutes) / 60.0
        )


@dataclass(frozen=True)
class RouteStats:
    count: int = 0
    reward_sum: float = 0.0
    success_count: int = 0

    @property
    def mean_reward(self) -> float:
        return self.reward_sum / self.count if self.count else 0.0

    @property
    def success_rate(self) -> float:
        return self.success_count / self.count if self.count else 0.0


class OutcomeLedger:
    """Append-style aggregate of verified route outcomes.

    The ledger stores only externally scored outcomes. Model self-assessment is not
    accepted as an outcome source by this class's contract.
    """

    def __init__(self) -> None:
        self._stats: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], RouteStats] = {}

    def record(self, outcome: RouteOutcome) -> None:
        key = (outcome.task_class, outcome.signature)
        current = self._stats.get(key, RouteStats())
        self._stats[key] = RouteStats(
            count=current.count + 1,
            reward_sum=current.reward_sum + outcome.reward,
            success_count=current.success_count + (1 if outcome.success else 0),
        )

    def stats(self, task_class: str, signature: Tuple[Tuple[str, str], ...]) -> RouteStats:
        return self._stats.get((task_class, signature), RouteStats())

    def total_observations(self, task_class: str) -> int:
        return sum(
            stats.count
            for (klass, _), stats in self._stats.items()
            if klass == task_class
        )


@dataclass(frozen=True)
class AdaptiveAdvice:
    incumbent: PlannedRoute
    shadow_challenger: Optional[PlannedRoute]
    incumbent_stats: RouteStats
    challenger_stats: RouteStats
    reason: str


class AdaptiveRouteAdvisor:
    """Learn from evidence without allowing learned policy to bypass hard gates.

    The advisor never auto-promotes a challenger. It chooses a normal incumbent
    using the deterministic global compiler, then suggests at most one already
    policy-qualified Pareto route for shadow/matched evaluation. Promotion stays
    with the external Evolution/Proof court.
    """

    def __init__(
        self,
        compiler: GlobalCapabilityCompiler,
        ledger: OutcomeLedger,
        exploration_strength: float = 0.35,
    ) -> None:
        self.compiler = compiler
        self.ledger = ledger
        self.exploration_strength = exploration_strength

    def advise(
        self,
        task_class: str,
        profile: CapabilityProfile,
        policy: RoutePolicy = RoutePolicy(),
        preferences: RoutePreferences = RoutePreferences(),
    ) -> AdaptiveAdvice:
        incumbent = self.compiler.select(profile, policy, preferences)
        frontier = self.compiler.pareto_frontier(profile, policy)
        incumbent_sig = route_signature(incumbent)
        incumbent_stats = self.ledger.stats(task_class, incumbent_sig)
        total = max(1, self.ledger.total_observations(task_class))

        challenger = None
        challenger_stats = RouteStats()
        best_ucb = float("-inf")
        for route in frontier:
            sig = route_signature(route)
            if sig == incumbent_sig:
                continue
            stats = self.ledger.stats(task_class, sig)
            bonus = self.exploration_strength * sqrt(log(total + 1.0) / (stats.count + 1.0))
            # Untried routes receive a bounded exploration bonus; route quality,
            # proof and policy have already been hard-gated by the compiler.
            ucb = stats.mean_reward + bonus
            if ucb > best_ucb:
                best_ucb = ucb
                challenger = route
                challenger_stats = stats

        if challenger is None:
            reason = "No distinct policy-qualified Pareto challenger."
        elif challenger_stats.count == 0:
            reason = "Untried qualified Pareto route selected for shadow evaluation only."
        else:
            reason = "Qualified Pareto challenger selected from observed reward plus bounded uncertainty bonus."

        return AdaptiveAdvice(
            incumbent=incumbent,
            shadow_challenger=challenger,
            incumbent_stats=incumbent_stats,
            challenger_stats=challenger_stats,
            reason=reason,
        )
