"""CFBE Ω Chat Hyperperformance Fabric v1.

Clean-room execution-planning primitives harvested from public orchestration patterns:
- durable/checkpointed workflows (Temporal/LangGraph/AutoGen),
- transactional cache + locking semantics (Prefect),
- trace-first observability (OpenAI Agents SDK/Dagster),
- metric-driven program optimization (DSPy),
- Human-First/Outcome-First owner-interruption discipline.

The module is provider-neutral and effect-free. It does not perform external actions.
It compiles work into bounded waves, chooses proven routes, reuses fresh results,
adapts concurrency, and turns observed failures into regression candidates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
import math
from statistics import quantiles
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "CFBE-CHAT-HYPERPERFORMANCE-V1"
VERSION = "1.0.0"


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


class EffectClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    INTERNAL_WRITE = "INTERNAL_WRITE"
    EXTERNAL_EFFECT = "EXTERNAL_EFFECT"


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    max_parallel: int = 8
    target_p95_ms: int = 2500
    max_owner_interrupts: int = 1
    max_retries_per_unit: int = 2
    context_token_budget: int = 16000

    def validate(self) -> None:
        if self.max_parallel < 1:
            raise ValueError("MAX_PARALLEL_INVALID")
        if self.target_p95_ms < 1:
            raise ValueError("TARGET_P95_INVALID")
        if self.max_owner_interrupts < 0:
            raise ValueError("OWNER_INTERRUPT_BUDGET_INVALID")
        if self.max_retries_per_unit < 0:
            raise ValueError("RETRY_BUDGET_INVALID")
        if self.context_token_budget < 256:
            raise ValueError("CONTEXT_BUDGET_TOO_SMALL")


@dataclass(frozen=True, slots=True)
class WorkUnit:
    unit_id: str
    surface: str
    operation: str
    input_fingerprint: str
    deps: tuple[str, ...] = ()
    effect_class: EffectClass = EffectClass.READ_ONLY
    batch_key: str = ""
    cacheable: bool = True
    freshness_key: str = ""
    estimated_ms: int = 1000
    priority: int = 50
    value_weight: float = 1.0
    privacy_class: str = "P1_INTERNAL"
    owner_only: bool = False

    def validate(self) -> None:
        if not all((self.unit_id.strip(), self.surface.strip(), self.operation.strip(), self.input_fingerprint.strip())):
            raise ValueError("WORK_UNIT_IDENTITY_REQUIRED")
        if self.estimated_ms < 0:
            raise ValueError("WORK_UNIT_ESTIMATE_INVALID")
        if self.effect_class is EffectClass.EXTERNAL_EFFECT and self.cacheable:
            raise ValueError("EXTERNAL_EFFECT_CANNOT_BE_RESULT_CACHED")

    @property
    def semantic_key(self) -> str:
        return digest({
            "surface": self.surface,
            "operation": self.operation,
            "input": self.input_fingerprint,
            "effect": self.effect_class.value,
            "freshness": self.freshness_key,
        })


@dataclass(frozen=True, slots=True)
class RouteProfile:
    route_id: str
    surface: str
    available: bool = True
    fresh: bool = True
    direct: bool = True
    success_rate: float = 1.0
    semantic_readback_rate: float = 1.0
    p95_ms: int = 1000
    unit_cost: float = 0.0
    circuit_open: bool = False
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.route_id.strip() or not self.surface.strip():
            raise ValueError("ROUTE_IDENTITY_REQUIRED")
        for value in (self.success_rate, self.semantic_readback_rate):
            if not 0.0 <= value <= 1.0:
                raise ValueError("ROUTE_RATE_INVALID")
        if self.p95_ms < 0 or self.unit_cost < 0:
            raise ValueError("ROUTE_METRIC_INVALID")
        if self.available and not self.proof_refs:
            raise ValueError("AVAILABLE_ROUTE_REQUIRES_PROOF")


@dataclass(frozen=True, slots=True)
class CacheRecord:
    semantic_key: str
    result_ref: str
    proof_ref: str
    freshness_key: str
    valid: bool = True


@dataclass(frozen=True, slots=True)
class RouteDecision:
    unit_id: str
    route_id: str
    state: str
    score: float
    reasons: tuple[str, ...]
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlannedUnit:
    unit: WorkUnit
    route: RouteDecision | None
    state: str
    cache_ref: str = ""
    deduplicated_to: str = ""


@dataclass(frozen=True, slots=True)
class ExecutionWave:
    wave_index: int
    unit_ids: tuple[str, ...]
    barrier: bool = False
    estimated_ms: int = 0


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    plan_id: str
    planned_units: tuple[PlannedUnit, ...]
    waves: tuple[ExecutionWave, ...]
    predicted_critical_path_ms: int
    cache_hits: int
    deduplicated_units: int
    blocked_units: tuple[str, ...]
    max_parallel: int


class RouteSelector:
    """Freshness/readback-weighted route choice with latency and cost pressure."""

    def __init__(self, *, target_p95_ms: int = 2500) -> None:
        self.target_p95_ms = max(1, int(target_p95_ms))

    def choose(self, unit: WorkUnit, routes: Sequence[RouteProfile]) -> RouteDecision:
        unit.validate()
        candidates: list[tuple[float, RouteProfile, tuple[str, ...]]] = []
        for route in routes:
            route.validate()
            if route.surface != unit.surface:
                continue
            reasons: list[str] = []
            if not route.available:
                reasons.append("UNAVAILABLE")
            if not route.fresh:
                reasons.append("STALE")
            if route.circuit_open:
                reasons.append("CIRCUIT_OPEN")
            if unit.effect_class is not EffectClass.READ_ONLY and route.semantic_readback_rate < 0.95:
                reasons.append("READBACK_BELOW_EFFECT_FLOOR")
            if reasons:
                continue
            latency_score = min(1.0, self.target_p95_ms / max(1.0, float(route.p95_ms)))
            cost_score = 1.0 / (1.0 + route.unit_cost)
            direct_bonus = 1.0 if route.direct else 0.0
            score = (
                0.30 * route.success_rate
                + 0.30 * route.semantic_readback_rate
                + 0.20 * latency_score
                + 0.10 * cost_score
                + 0.10 * direct_bonus
            )
            candidates.append((score, route, ("FRESH_PROVEN_ROUTE", "SEMANTIC_READBACK_WEIGHTED")))
        if not candidates:
            return RouteDecision(unit.unit_id, "", "NO_ELIGIBLE_ROUTE", 0.0, ("NO_FRESH_PROVEN_ROUTE",))
        score, route, reasons = max(candidates, key=lambda item: (item[0], item[1].success_rate, -item[1].p95_ms, item[1].route_id))
        return RouteDecision(unit.unit_id, route.route_id, "ROUTE_SELECTED", round(score, 6), reasons, route.proof_refs)


class FreshResultCache:
    """Content-addressed result reuse; freshness mismatch fails closed."""

    def __init__(self, records: Iterable[CacheRecord] = ()) -> None:
        self._records = {r.semantic_key: r for r in records if r.valid}

    def lookup(self, unit: WorkUnit) -> CacheRecord | None:
        if not unit.cacheable or unit.effect_class is EffectClass.EXTERNAL_EFFECT:
            return None
        record = self._records.get(unit.semantic_key)
        if record is None:
            return None
        if unit.freshness_key and record.freshness_key != unit.freshness_key:
            return None
        if not record.proof_ref:
            return None
        return record


class HyperperformancePlanner:
    """Compile work into deduplicated, cached, dependency-safe parallel waves."""

    def __init__(self, budget: PerformanceBudget, selector: RouteSelector | None = None) -> None:
        budget.validate()
        self.budget = budget
        self.selector = selector or RouteSelector(target_p95_ms=budget.target_p95_ms)

    def compile(
        self,
        units: Sequence[WorkUnit],
        routes: Sequence[RouteProfile],
        cache: FreshResultCache | None = None,
    ) -> ExecutionPlan:
        cache = cache or FreshResultCache()
        by_id: dict[str, WorkUnit] = {}
        for unit in units:
            unit.validate()
            if unit.unit_id in by_id:
                raise ValueError("DUPLICATE_UNIT_ID")
            by_id[unit.unit_id] = unit
        for unit in units:
            missing = sorted(set(unit.deps) - set(by_id))
            if missing:
                raise ValueError("MISSING_DEPENDENCY:" + ",".join(missing))

        semantic_owner: dict[str, str] = {}
        planned: dict[str, PlannedUnit] = {}
        cache_hits = 0
        dedup = 0
        for unit in sorted(units, key=lambda u: (-u.priority, u.unit_id)):
            if unit.effect_class is not EffectClass.EXTERNAL_EFFECT and unit.cacheable:
                owner = semantic_owner.get(unit.semantic_key)
                if owner:
                    planned[unit.unit_id] = PlannedUnit(unit, None, "DEDUPLICATED", deduplicated_to=owner)
                    dedup += 1
                    continue
                semantic_owner[unit.semantic_key] = unit.unit_id
            hit = cache.lookup(unit)
            if hit:
                planned[unit.unit_id] = PlannedUnit(unit, None, "CACHE_HIT", cache_ref=hit.result_ref)
                cache_hits += 1
                continue
            decision = self.selector.choose(unit, routes)
            state = "READY" if decision.state == "ROUTE_SELECTED" else "BLOCKED"
            planned[unit.unit_id] = PlannedUnit(unit, decision, state)

        completed = {uid for uid, pu in planned.items() if pu.state in {"CACHE_HIT", "DEDUPLICATED"}}
        blocked = {uid for uid, pu in planned.items() if pu.state == "BLOCKED"}
        remaining = {uid for uid, pu in planned.items() if pu.state == "READY"}
        waves: list[ExecutionWave] = []
        wave_index = 0

        while remaining:
            ready = [uid for uid in remaining if set(by_id[uid].deps) <= completed]
            if not ready:
                # If only blocked dependencies remain, propagate blocking; otherwise graph cycle.
                propagated = [uid for uid in remaining if set(by_id[uid].deps) & blocked]
                if propagated:
                    for uid in propagated:
                        remaining.remove(uid)
                        blocked.add(uid)
                    continue
                raise ValueError("DEPENDENCY_CYCLE_DETECTED")

            effects = sorted(
                (uid for uid in ready if by_id[uid].effect_class is EffectClass.EXTERNAL_EFFECT),
                key=lambda uid: (-by_id[uid].priority, uid),
            )
            if effects:
                selected = [effects[0]]
                barrier = True
            else:
                selected = sorted(ready, key=lambda uid: (-by_id[uid].priority, by_id[uid].estimated_ms, uid))[: self.budget.max_parallel]
                barrier = False
            estimated = max((by_id[uid].estimated_ms for uid in selected), default=0)
            waves.append(ExecutionWave(wave_index, tuple(selected), barrier, estimated))
            wave_index += 1
            for uid in selected:
                remaining.remove(uid)
                completed.add(uid)

        critical = sum(w.estimated_ms for w in waves)
        ordered_planned = tuple(planned[u.unit_id] for u in units)
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "units": [asdict(p) for p in ordered_planned],
            "waves": [asdict(w) for w in waves],
            "budget": asdict(self.budget),
        }
        return ExecutionPlan(
            plan_id="cfbe_plan_" + digest(material).split(":", 1)[1][:20],
            planned_units=ordered_planned,
            waves=tuple(waves),
            predicted_critical_path_ms=critical,
            cache_hits=cache_hits,
            deduplicated_units=dedup,
            blocked_units=tuple(sorted(blocked)),
            max_parallel=self.budget.max_parallel,
        )


@dataclass(frozen=True, slots=True)
class SpanObservation:
    span_id: str
    unit_id: str
    latency_ms: int
    success: bool
    semantic_readback_ok: bool
    retries: int = 0
    duplicate_work: bool = False
    avoidable_owner_interrupt: bool = False
    claim_mismatch: bool = False


@dataclass(frozen=True, slots=True)
class AdaptiveState:
    concurrency: int
    p95_ms: int
    failure_rate: float
    semantic_failure_rate: float
    action: str


class AdaptiveConcurrencyController:
    """AIMD-style concurrency control using observed latency and semantic failures."""

    def __init__(self, budget: PerformanceBudget, *, initial: int = 2) -> None:
        budget.validate()
        self.budget = budget
        self.concurrency = min(max(1, initial), budget.max_parallel)

    def observe(self, spans: Sequence[SpanObservation]) -> AdaptiveState:
        if not spans:
            return AdaptiveState(self.concurrency, 0, 0.0, 0.0, "NO_CHANGE")
        latencies = sorted(max(0, s.latency_ms) for s in spans)
        if len(latencies) == 1:
            p95 = latencies[0]
        else:
            p95 = int(quantiles(latencies, n=20, method="inclusive")[18])
        failure_rate = sum(not s.success for s in spans) / len(spans)
        semantic_failure = sum(not s.semantic_readback_ok for s in spans) / len(spans)
        unhealthy = failure_rate > 0.10 or semantic_failure > 0.05 or p95 > self.budget.target_p95_ms
        if unhealthy:
            self.concurrency = max(1, math.ceil(self.concurrency / 2))
            action = "MULTIPLICATIVE_DECREASE"
        elif self.concurrency < self.budget.max_parallel:
            self.concurrency += 1
            action = "ADDITIVE_INCREASE"
        else:
            action = "AT_MAX_HEALTHY"
        return AdaptiveState(self.concurrency, p95, round(failure_rate, 6), round(semantic_failure, 6), action)


@dataclass(frozen=True, slots=True)
class ContextItem:
    item_id: str
    text_ref: str
    token_estimate: int
    relevance: float
    recency: float
    proof_bearing: bool = False
    decision_bearing: bool = False
    unresolved_gap: bool = False

    @property
    def utility(self) -> float:
        return (
            self.relevance * 0.45
            + self.recency * 0.15
            + (0.20 if self.proof_bearing else 0.0)
            + (0.12 if self.decision_bearing else 0.0)
            + (0.08 if self.unresolved_gap else 0.0)
        ) / max(1, self.token_estimate)


@dataclass(frozen=True, slots=True)
class ContextPack:
    selected_ids: tuple[str, ...]
    dropped_ids: tuple[str, ...]
    token_estimate: int
    fingerprint: str


class ContextBudgeter:
    """Proof-aware working-set compaction for long chats."""

    def compile(self, items: Sequence[ContextItem], token_budget: int) -> ContextPack:
        if token_budget < 1:
            raise ValueError("TOKEN_BUDGET_INVALID")
        mandatory = [i for i in items if i.proof_bearing or i.decision_bearing or i.unresolved_gap]
        optional = [i for i in items if i not in mandatory]
        selected: list[ContextItem] = []
        used = 0
        for item in sorted(mandatory, key=lambda x: (-x.utility, x.item_id)):
            if used + item.token_estimate <= token_budget:
                selected.append(item)
                used += item.token_estimate
        for item in sorted(optional, key=lambda x: (-x.utility, x.item_id)):
            if used + item.token_estimate <= token_budget:
                selected.append(item)
                used += item.token_estimate
        ids = tuple(i.item_id for i in selected)
        dropped = tuple(i.item_id for i in items if i.item_id not in set(ids))
        return ContextPack(ids, dropped, used, digest({"selected": ids, "budget": token_budget}))


@dataclass(frozen=True, slots=True)
class RegressionCandidate:
    regression_id: str
    unit_id: str
    failure_classes: tuple[str, ...]
    severity: str
    deterministic_key: str


class TraceToRegression:
    """Convert observed trajectory defects into deterministic regression candidates."""

    def compile(self, spans: Iterable[SpanObservation]) -> tuple[RegressionCandidate, ...]:
        out: list[RegressionCandidate] = []
        for span in spans:
            failures: list[str] = []
            if not span.success:
                failures.append("EXECUTION_FAILURE")
            if not span.semantic_readback_ok:
                failures.append("SEMANTIC_READBACK_FAILURE")
            if span.duplicate_work:
                failures.append("DUPLICATE_WORK")
            if span.avoidable_owner_interrupt:
                failures.append("AVOIDABLE_OWNER_INTERRUPT")
            if span.claim_mismatch:
                failures.append("CLAIM_PROOF_MISMATCH")
            if not failures:
                continue
            key = digest({"unit": span.unit_id, "failures": sorted(failures)})
            severity = "P0" if any(x in failures for x in ("CLAIM_PROOF_MISMATCH", "SEMANTIC_READBACK_FAILURE")) else "P1"
            out.append(RegressionCandidate("reg_" + key.split(":", 1)[1][:16], span.unit_id, tuple(failures), severity, key))
        return tuple(out)


@dataclass(frozen=True, slots=True)
class OwnerEscalationState:
    material: bool
    owner_only: bool
    recovery_exhausted: bool
    safe_route_available: bool
    exact_decision_request: str = ""


def owner_interrupt_required(state: OwnerEscalationState) -> bool:
    """Human-First rule: no owner interruption while safe system-owned recovery remains."""
    if not state.material:
        return False
    if state.owner_only:
        return bool(state.exact_decision_request.strip())
    if state.safe_route_available and not state.recovery_exhausted:
        return False
    return state.recovery_exhausted and bool(state.exact_decision_request.strip())


__all__ = [
    "AdaptiveConcurrencyController", "AdaptiveState", "CacheRecord", "ContextBudgeter",
    "ContextItem", "ContextPack", "EffectClass", "ExecutionPlan", "ExecutionWave",
    "FreshResultCache", "HyperperformancePlanner", "OwnerEscalationState",
    "PerformanceBudget", "PlannedUnit", "RegressionCandidate", "RouteDecision",
    "RouteProfile", "RouteSelector", "SpanObservation", "TraceToRegression", "WorkUnit",
    "digest", "owner_interrupt_required",
]
