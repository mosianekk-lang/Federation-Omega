from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from federation.of50_ace_v1 import FrictionClass, CycleDecision


class ConstraintKind(str, Enum):
    ACTIVE_TASK_LIMIT = "ACTIVE_TASK_LIMIT"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    CONCURRENCY_LIMIT = "CONCURRENCY_LIMIT"
    STORAGE_LIMIT = "STORAGE_LIMIT"
    PROVIDER_CAPACITY = "PROVIDER_CAPACITY"
    GENERIC_CAPACITY = "GENERIC_CAPACITY"
    UNKNOWN = "UNKNOWN"


class RerouteState(str, Enum):
    REUSE_EXISTING = "REUSE_EXISTING"
    CONSOLIDATE_EQUIVALENT = "CONSOLIDATE_EQUIVALENT"
    REROUTED = "REROUTED"
    DURABLE_QUEUE = "DURABLE_QUEUE"
    NO_SAFE_ROUTE = "NO_SAFE_ROUTE"


@dataclass(frozen=True)
class ConstraintEvent:
    message: str
    surface_id: str
    operation: str
    mission_id: str
    prior_route_family: str = ""
    recurrence: int = 1


@dataclass(frozen=True)
class MissionNeeds:
    scheduled: bool = False
    recurring: bool = False
    condition_watch: bool = False
    immediate_allowed: bool = True
    external_effect_required: bool = False


@dataclass(frozen=True)
class RouteOption:
    route_id: str
    route_family: str
    callable_now: bool = True
    current: bool = True
    preserves_semantics: bool = True
    supports_schedule: bool = False
    supports_recurring: bool = False
    supports_condition_watch: bool = False
    supports_immediate: bool = True
    external_effect_authorized: bool = False
    failure_domain: str = ""
    owner_burden: float = 0.0
    monetary_cost: float = 0.0
    reliability: float = 1.0
    proof_strength: float = 1.0


@dataclass(frozen=True)
class RerouteDecision:
    state: RerouteState
    constraint_kind: ConstraintKind
    selected_route_id: str
    selected_route_family: str
    reason: str
    of50_friction_class: FrictionClass = FrictionClass.RATE_OR_QUOTA_PRESSURE
    cycle_decision: CycleDecision = CycleDecision.CHANGED_ROUTE_REQUIRED
    preserve_mission: bool = True
    owner_action_required: bool = False


_PATTERNS = (
    (ConstraintKind.ACTIVE_TASK_LIMIT, (
        "limit of 20 active tasks", "too many active tasks", "active task limit",
        "too_many_active_automations", "maximum active tasks", "max active tasks",
    )),
    (ConstraintKind.RATE_LIMIT, (
        "rate limit", "too many requests", "http 429", "status 429", "throttled", "throttling",
    )),
    (ConstraintKind.QUOTA_EXHAUSTED, (
        "quota exceeded", "quota exhausted", "usage limit", "credits exhausted", "credit limit",
    )),
    (ConstraintKind.CONCURRENCY_LIMIT, (
        "concurrency limit", "too many concurrent", "maximum concurrent", "concurrent jobs limit",
    )),
    (ConstraintKind.STORAGE_LIMIT, (
        "storage full", "storage limit", "disk quota", "insufficient storage", "out of space",
    )),
    (ConstraintKind.PROVIDER_CAPACITY, (
        "provider capacity", "capacity temporarily unavailable", "overloaded", "server overloaded",
    )),
    (ConstraintKind.GENERIC_CAPACITY, (
        "reached your limit", "limit reached", "capacity full", "maximum reached", "no slots available",
    )),
)


class GlobalConstraintRerouter:
    """Constraint -> changed-route adapter for OF50/Alpha-Omega/FDOF consumers.

    It preserves mission semantics and never disables unrelated work merely to free capacity.
    """

    @staticmethod
    def classify(message: str) -> ConstraintKind:
        text = " ".join(str(message).casefold().split())
        for kind, patterns in _PATTERNS:
            if any(p in text for p in patterns):
                return kind
        return ConstraintKind.UNKNOWN

    @staticmethod
    def _fits(needs: MissionNeeds, route: RouteOption) -> bool:
        if not (route.callable_now and route.current and route.preserves_semantics):
            return False
        if needs.scheduled and not route.supports_schedule:
            return False
        if needs.recurring and not route.supports_recurring:
            return False
        if needs.condition_watch and not route.supports_condition_watch:
            return False
        if not needs.scheduled and needs.immediate_allowed and not route.supports_immediate:
            return False
        if needs.external_effect_required and not route.external_effect_authorized:
            return False
        return True

    @staticmethod
    def _score(route: RouteOption):
        return (route.proof_strength, route.reliability, -route.owner_burden, -route.monetary_cost, route.route_id)

    def decide(
        self,
        event: ConstraintEvent,
        needs: MissionNeeds,
        routes: Iterable[RouteOption],
        *,
        equivalent_existing_route_id: str = "",
        equivalent_existing_route_family: str = "",
        safe_equivalent_consolidation: bool = False,
    ) -> RerouteDecision:
        kind = self.classify(event.message)

        if equivalent_existing_route_id:
            return RerouteDecision(
                RerouteState.REUSE_EXISTING, kind,
                equivalent_existing_route_id, equivalent_existing_route_family,
                "SEMANTICALLY_EQUIVALENT_EXISTING_WORK_REUSED",
            )

        if safe_equivalent_consolidation:
            return RerouteDecision(
                RerouteState.CONSOLIDATE_EQUIVALENT, kind,
                "existing-equivalent-work", "CONSOLIDATED_EXISTING",
                "ONLY_SEMANTICALLY_EQUIVALENT_DUPLICATES_MAY_BE_CONSOLIDATED",
            )

        viable = [r for r in routes if self._fits(needs, r)]

        if event.recurrence >= 2 and event.prior_route_family:
            changed = [r for r in viable if r.route_family != event.prior_route_family]
            if changed:
                viable = changed

        if viable:
            viable.sort(key=self._score, reverse=True)
            r = viable[0]
            return RerouteDecision(
                RerouteState.REROUTED, kind, r.route_id, r.route_family,
                "CONSTRAINT_INTERCEPTED_MISSION_PRESERVED_CHANGED_ROUTE_SELECTED",
            )

        return RerouteDecision(
            RerouteState.DURABLE_QUEUE, kind,
            "fuse-durable-mission-queue", "DURABLE_QUEUE",
            "NO_SEMANTICALLY_EQUIVALENT_LIVE_ROUTE_MISSION_RETAINED_FOR_CHANGED_MECHANISM_OR_CAPACITY_RELEASE",
            owner_action_required=False,
        )


def default_constraint_routes() -> tuple[RouteOption, ...]:
    return (
        RouteOption("fuse-internal-scheduler", "FUSE_INTERNAL_SCHEDULER", supports_schedule=True, supports_recurring=True, supports_condition_watch=True, supports_immediate=False),
        RouteOption("provider-native-scheduler", "PROVIDER_NATIVE_SCHEDULER", supports_schedule=True, supports_recurring=True, supports_condition_watch=True, supports_immediate=False),
        RouteOption("windows-task-scheduler", "LOCAL_WINDOWS_SCHEDULER", supports_schedule=True, supports_recurring=True, supports_condition_watch=False, supports_immediate=False),
        RouteOption("local-fuse-runtime", "LOCAL_RUNTIME", supports_immediate=True),
        RouteOption("alternate-provider", "ALTERNATE_PROVIDER", supports_immediate=True),
        RouteOption("foreground-execution", "IMMEDIATE_FOREGROUND", supports_immediate=True),
    )
