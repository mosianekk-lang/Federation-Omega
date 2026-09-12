from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .kernel import CapabilityProfile, CapabilityRegistry, Implementation


@dataclass(frozen=True)
class ImplementationMeta:
    """Route-level metadata kept outside provider/model adapters.

    confidence is evidence confidence for the measured implementation metrics,
    not model self-confidence. requires_tags/provides_tags express cross-organ
    compatibility without leaking provider syntax into mission semantics.
    """

    implementation: Implementation
    confidence: float = 1.0
    owner_intervention_minutes: float = 0.0
    failure_probability: float = 0.0
    provides_tags: Tuple[str, ...] = ()
    requires_tags: Tuple[str, ...] = ()
    forbidden_with_providers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RoutePolicy:
    max_total_cost_units: Optional[float] = None
    max_worst_latency_ms: Optional[float] = None
    min_average_quality: float = 0.0
    min_average_sovereignty: float = 0.0
    min_evidence_confidence: float = 0.0
    max_provider_concentration: float = 1.0
    min_local_fraction: float = 0.0
    max_owner_intervention_minutes: Optional[float] = None
    max_failure_probability: Optional[float] = None
    forbidden_providers: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RoutePreferences:
    quality_weight: float = 3.0
    sovereignty_weight: float = 1.5
    cost_weight: float = 1.0
    latency_weight: float = 0.5
    concentration_weight: float = 0.8
    local_weight: float = 0.5
    intervention_weight: float = 0.5
    failure_weight: float = 2.0
    confidence_weight: float = 1.0


@dataclass(frozen=True)
class PlannedRoute:
    profile_id: str
    selected: Mapping[str, ImplementationMeta]
    total_cost_units: float
    worst_latency_ms: float
    average_quality: float
    average_sovereignty: float
    provider_concentration: float
    local_fraction: float
    min_evidence_confidence: float
    owner_intervention_minutes: float
    aggregate_failure_probability: float

    @property
    def providers(self) -> Set[str]:
        return {m.implementation.provider for m in self.selected.values()}

    @property
    def astra_independent(self) -> bool:
        return "openai" not in self.providers


class RoutePlanningError(RuntimeError):
    pass


class GlobalCapabilityCompiler:
    """Compile whole routes instead of greedily selecting each capability.

    Hard quality/authority/safety/proof gates happen before route generation.
    Cross-capability tag constraints then eliminate semantically incompatible
    combinations. The surviving routes are filtered by mission policy, reduced
    to a Pareto frontier, and only then ranked by owner preferences.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        implementations: Iterable[ImplementationMeta | Implementation],
    ) -> None:
        self.registry = registry
        self._impls: Dict[str, List[ImplementationMeta]] = {}
        for item in implementations:
            meta = item if isinstance(item, ImplementationMeta) else ImplementationMeta(item)
            self._impls.setdefault(meta.implementation.capability_id, []).append(meta)

    def _candidates(self, profile: CapabilityProfile, cap_id: str) -> List[ImplementationMeta]:
        self.registry.get(cap_id)
        out = []
        for meta in self._impls.get(cap_id, ()):  # hard gates first
            impl = meta.implementation
            if not impl.satisfies(
                min_quality=profile.min_quality,
                min_maturity=profile.min_maturity,
            ):
                continue
            if profile.require_astra_independent and impl.provider == "openai":
                continue
            out.append(meta)
        return out

    @staticmethod
    def _compatible(items: Sequence[ImplementationMeta]) -> bool:
        providers = {m.implementation.provider for m in items}
        tags = {tag for m in items for tag in m.provides_tags}
        for meta in items:
            if not set(meta.requires_tags).issubset(tags):
                return False
            if providers.intersection(meta.forbidden_with_providers):
                return False
        return True

    @staticmethod
    def _metrics(profile_id: str, selected: Mapping[str, ImplementationMeta]) -> PlannedRoute:
        metas = list(selected.values())
        impls = [m.implementation for m in metas]
        n = len(impls)
        provider_counts: Dict[str, int] = {}
        for impl in impls:
            provider_counts[impl.provider] = provider_counts.get(impl.provider, 0) + 1
        concentration = max(provider_counts.values(), default=0) / n if n else 0.0
        local_fraction = sum(1 for i in impls if i.local) / n if n else 0.0
        # Independent branch failure approximation: P(any selected component fails).
        survival = 1.0
        for meta in metas:
            survival *= max(0.0, min(1.0, 1.0 - meta.failure_probability))
        return PlannedRoute(
            profile_id=profile_id,
            selected=dict(selected),
            total_cost_units=sum(i.cost_units for i in impls),
            worst_latency_ms=max((i.latency_ms for i in impls), default=0.0),
            average_quality=sum(i.quality for i in impls) / n if n else 0.0,
            average_sovereignty=sum(i.sovereignty for i in impls) / n if n else 0.0,
            provider_concentration=concentration,
            local_fraction=local_fraction,
            min_evidence_confidence=min((m.confidence for m in metas), default=1.0),
            owner_intervention_minutes=sum(m.owner_intervention_minutes for m in metas),
            aggregate_failure_probability=1.0 - survival,
        )

    @staticmethod
    def _passes_policy(route: PlannedRoute, policy: RoutePolicy) -> bool:
        if policy.max_total_cost_units is not None and route.total_cost_units > policy.max_total_cost_units:
            return False
        if policy.max_worst_latency_ms is not None and route.worst_latency_ms > policy.max_worst_latency_ms:
            return False
        if route.average_quality < policy.min_average_quality:
            return False
        if route.average_sovereignty < policy.min_average_sovereignty:
            return False
        if route.min_evidence_confidence < policy.min_evidence_confidence:
            return False
        if route.provider_concentration > policy.max_provider_concentration:
            return False
        if route.local_fraction < policy.min_local_fraction:
            return False
        if (
            policy.max_owner_intervention_minutes is not None
            and route.owner_intervention_minutes > policy.max_owner_intervention_minutes
        ):
            return False
        if (
            policy.max_failure_probability is not None
            and route.aggregate_failure_probability > policy.max_failure_probability
        ):
            return False
        if route.providers.intersection(policy.forbidden_providers):
            return False
        return True

    def enumerate_routes(
        self,
        profile: CapabilityProfile,
        policy: RoutePolicy = RoutePolicy(),
    ) -> Tuple[PlannedRoute, ...]:
        candidate_lists: List[List[ImplementationMeta]] = []
        for cap_id in profile.required_capabilities:
            candidates = self._candidates(profile, cap_id)
            if not candidates:
                raise RoutePlanningError(f"no hard-gate-qualified implementation for {cap_id}")
            candidate_lists.append(candidates)

        routes: List[PlannedRoute] = []
        for combo in product(*candidate_lists):
            if not self._compatible(combo):
                continue
            selected = {
                cap_id: meta for cap_id, meta in zip(profile.required_capabilities, combo)
            }
            route = self._metrics(profile.profile_id, selected)
            if profile.require_astra_independent and not route.astra_independent:
                continue
            if self._passes_policy(route, policy):
                routes.append(route)
        return tuple(routes)

    @staticmethod
    def _dominates(a: PlannedRoute, b: PlannedRoute) -> bool:
        """True when a is no worse on every objective and better on at least one."""
        a_vals = (
            -a.average_quality,
            -a.average_sovereignty,
            a.total_cost_units,
            a.worst_latency_ms,
            a.provider_concentration,
            -a.local_fraction,
            -a.min_evidence_confidence,
            a.owner_intervention_minutes,
            a.aggregate_failure_probability,
        )
        b_vals = (
            -b.average_quality,
            -b.average_sovereignty,
            b.total_cost_units,
            b.worst_latency_ms,
            b.provider_concentration,
            -b.local_fraction,
            -b.min_evidence_confidence,
            b.owner_intervention_minutes,
            b.aggregate_failure_probability,
        )
        return all(x <= y for x, y in zip(a_vals, b_vals)) and any(
            x < y for x, y in zip(a_vals, b_vals)
        )

    def pareto_frontier(
        self,
        profile: CapabilityProfile,
        policy: RoutePolicy = RoutePolicy(),
    ) -> Tuple[PlannedRoute, ...]:
        routes = self.enumerate_routes(profile, policy)
        frontier = [
            route
            for route in routes
            if not any(
                other is not route and self._dominates(other, route)
                for other in routes
            )
        ]
        return tuple(frontier)

    @staticmethod
    def _preference_score(route: PlannedRoute, pref: RoutePreferences) -> float:
        return (
            pref.cost_weight * route.total_cost_units
            + pref.latency_weight * (route.worst_latency_ms / 10000.0)
            + pref.concentration_weight * route.provider_concentration
            + pref.intervention_weight * (route.owner_intervention_minutes / 60.0)
            + pref.failure_weight * route.aggregate_failure_probability
            - pref.quality_weight * route.average_quality
            - pref.sovereignty_weight * route.average_sovereignty
            - pref.local_weight * route.local_fraction
            - pref.confidence_weight * route.min_evidence_confidence
        )

    def select(
        self,
        profile: CapabilityProfile,
        policy: RoutePolicy = RoutePolicy(),
        preferences: RoutePreferences = RoutePreferences(),
    ) -> PlannedRoute:
        frontier = self.pareto_frontier(profile, policy)
        if not frontier:
            raise RoutePlanningError(f"no policy-qualified route for {profile.profile_id}")
        return min(
            frontier,
            key=lambda route: (
                self._preference_score(route, preferences),
                tuple(sorted(m.implementation.impl_id for m in route.selected.values())),
            ),
        )
