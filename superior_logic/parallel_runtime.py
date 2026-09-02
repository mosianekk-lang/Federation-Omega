from __future__ import annotations

"""Bounded SLOS parallel runtime harvested from PR #1025.

This module deliberately extracts only the runtime primitives that remain useful
beyond the already-admitted SLOS 3.3 MissionIR/digital-twin control plane:

- critical-path + value-of-information bounded beam lane selection;
- conflict-domain fencing;
- TokenBucket fan-out budgeting through the existing SOL 6.2 primitive;
- deterministic work stealing;
- real asyncio fan-out/fan-in for NO_EFFECT / READ_ONLY lanes;
- semantically verified read-route races and straggler hedging.

Authority boundary
------------------
This is not a provider executor or authority plane. MUTATING lanes are rejected
*before* the supplied runner is invoked. Provider mutation remains owned by the
existing SOL/SOVARA admission path. Results from NO_EFFECT / READ_ONLY runners
that report a provider effect fail closed. Source admission therefore proves only
bounded local/runtime semantics; it does not authorize external effects or claim
production performance superiority.
"""

import asyncio
import hashlib
import json
import math
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from sol_61_runtime.sol_62_frontier_primitives import TokenBucket

SCHEMA = "SLOS_PARALLEL_RUNTIME_HARVEST_V1"
ALGORITHM = "CP_VOI_CONFLICT_BOUNDED_BEAM_V1"


class ParallelRuntimeError(RuntimeError):
    pass


class LaneEffect(str, Enum):
    NO_EFFECT = "NO_EFFECT"
    READ_ONLY = "READ_ONLY"
    MUTATING = "MUTATING"


@dataclass(frozen=True, slots=True)
class LaneCandidate:
    lane_id: str
    transition_id: str
    expected_value: float
    uncertainty_reduction: float
    critical_path_ms: float
    estimated_latency_ms: float
    estimated_cost: float
    risk: float
    conflict_domains: tuple[str, ...] = ()
    route_ids: tuple[str, ...] = ()
    effect_class: LaneEffect = LaneEffect.NO_EFFECT
    reversible: bool = True

    def validate(self) -> "LaneCandidate":
        if not self.lane_id.strip() or not self.transition_id.strip():
            raise ValueError("SLOS_PARALLEL_LANE_IDENTITY_REQUIRED")
        if not 0.0 <= float(self.uncertainty_reduction) <= 1.0:
            raise ValueError("SLOS_PARALLEL_UNCERTAINTY_REDUCTION_OUT_OF_RANGE")
        if not 0.0 <= float(self.risk) <= 1.0:
            raise ValueError("SLOS_PARALLEL_RISK_OUT_OF_RANGE")
        if float(self.critical_path_ms) < 0 or float(self.estimated_latency_ms) < 0:
            raise ValueError("SLOS_PARALLEL_LATENCY_NEGATIVE")
        if float(self.estimated_cost) < 0:
            raise ValueError("SLOS_PARALLEL_COST_NEGATIVE")
        if not math.isfinite(float(self.expected_value)):
            raise ValueError("SLOS_PARALLEL_EXPECTED_VALUE_NONFINITE")
        if len(set(self.conflict_domains)) != len(self.conflict_domains):
            raise ValueError("SLOS_PARALLEL_DUPLICATE_CONFLICT_DOMAIN")
        if len(set(self.route_ids)) != len(self.route_ids):
            raise ValueError("SLOS_PARALLEL_DUPLICATE_ROUTE_ID")
        return self

    @property
    def value_of_information(self) -> float:
        seconds = max(float(self.estimated_latency_ms) / 1000.0, 0.001)
        return float(self.uncertainty_reduction) / seconds

    @property
    def priority(self) -> float:
        critical_seconds = float(self.critical_path_ms) / 1000.0
        return (
            2.50 * float(self.expected_value)
            + 1.75 * self.value_of_information
            + math.log1p(critical_seconds)
            - 1.50 * float(self.risk)
            - 0.20 * float(self.estimated_cost)
        )


@dataclass(frozen=True, slots=True)
class LanePlan:
    lane_id: str
    transition_id: str
    route_ids: tuple[str, ...]
    priority: float
    critical_path_ms: float
    value_of_information: float
    estimated_latency_ms: float
    estimated_cost: float
    risk: float
    conflict_domains: tuple[str, ...]
    effect_class: LaneEffect
    reversible: bool

    @property
    def mutating(self) -> bool:
        return self.effect_class is LaneEffect.MUTATING


@dataclass(frozen=True, slots=True)
class ParallelPlan:
    mission_id: str
    lanes: tuple[LanePlan, ...]
    deferred_lane_ids: tuple[str, ...]
    estimated_parallel_latency_ms: float
    estimated_serial_latency_ms: float
    theoretical_speedup: float
    algorithm: str
    plan_sha256: str
    provider_effect_authorized: bool = False
    stable_promotion_authorized: bool = False


@dataclass(frozen=True, slots=True)
class LaneExecutionResult:
    lane_id: str
    transition_id: str
    result: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ParallelRuntimeReceipt:
    schema: str
    mission_id: str
    plan_sha256: str
    planned_lane_count: int
    executed_lane_count: int
    mutating_lane_executed: bool
    provider_effect_observed: bool
    provider_effect_authorized: bool
    stable_promotion_authorized: bool
    receipt_sha256: str


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _lane_payload(lane: LanePlan) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "transition_id": lane.transition_id,
        "route_ids": lane.route_ids,
        "priority": round(lane.priority, 12),
        "critical_path_ms": lane.critical_path_ms,
        "value_of_information": round(lane.value_of_information, 12),
        "estimated_latency_ms": lane.estimated_latency_ms,
        "estimated_cost": lane.estimated_cost,
        "risk": lane.risk,
        "conflict_domains": lane.conflict_domains,
        "effect_class": lane.effect_class.value,
        "reversible": lane.reversible,
    }


def _to_plan(candidate: LaneCandidate) -> LanePlan:
    candidate.validate()
    return LanePlan(
        lane_id=candidate.lane_id,
        transition_id=candidate.transition_id,
        route_ids=tuple(candidate.route_ids),
        priority=float(candidate.priority),
        critical_path_ms=float(candidate.critical_path_ms),
        value_of_information=float(candidate.value_of_information),
        estimated_latency_ms=float(candidate.estimated_latency_ms),
        estimated_cost=float(candidate.estimated_cost),
        risk=float(candidate.risk),
        conflict_domains=tuple(sorted(candidate.conflict_domains)),
        effect_class=candidate.effect_class,
        reversible=bool(candidate.reversible),
    )


class BoundedParallelSelector:
    """Deterministic conflict-aware CP/VOI lane selector.

    It selects a compatible set of already-described work. It neither resolves
    provider routes nor grants authority. A TokenBucket, when supplied, is the
    existing SOL 6.2 primitive and bounds fan-out before beam selection.
    """

    def __init__(
        self,
        *,
        max_lanes: int = 8,
        beam_width: int = 32,
        token_bucket: TokenBucket | None = None,
    ) -> None:
        if not 1 <= int(max_lanes) <= 64:
            raise ValueError("SLOS_PARALLEL_MAX_LANES_OUT_OF_RANGE")
        if not 1 <= int(beam_width) <= 512:
            raise ValueError("SLOS_PARALLEL_BEAM_WIDTH_OUT_OF_RANGE")
        self.max_lanes = int(max_lanes)
        self.beam_width = int(beam_width)
        self.token_bucket = token_bucket

    def _beam_select(self, candidates: Sequence[LanePlan]) -> tuple[LanePlan, ...]:
        # score, lanes, occupied conflict domains, total estimated cost
        states: list[tuple[float, tuple[LanePlan, ...], frozenset[str], float]] = [
            (0.0, (), frozenset(), 0.0)
        ]
        ordered = sorted(candidates, key=lambda item: (-item.priority, item.lane_id))
        for candidate in ordered:
            next_states = list(states)
            candidate_domains = frozenset(candidate.conflict_domains)
            for score, lanes, occupied, cost in states:
                if len(lanes) >= self.max_lanes:
                    continue
                if occupied.intersection(candidate_domains):
                    continue
                next_states.append(
                    (
                        score + candidate.priority,
                        lanes + (candidate,),
                        occupied.union(candidate_domains),
                        cost + candidate.estimated_cost,
                    )
                )
            next_states.sort(
                key=lambda state: (
                    -state[0],
                    state[3],
                    tuple(item.lane_id for item in state[1]),
                )
            )
            states = next_states[: self.beam_width]

        best = states[0][1] if states else ()
        return tuple(sorted(best, key=lambda item: (-item.priority, item.lane_id)))

    def select(
        self,
        *,
        mission_id: str,
        candidates: Sequence[LaneCandidate],
        now_epoch: float = 0.0,
    ) -> ParallelPlan:
        if not mission_id.strip():
            raise ValueError("SLOS_PARALLEL_MISSION_ID_REQUIRED")
        if len({item.lane_id for item in candidates}) != len(candidates):
            raise ValueError("SLOS_PARALLEL_LANE_IDS_MUST_BE_UNIQUE")
        if len({item.transition_id for item in candidates}) != len(candidates):
            raise ValueError("SLOS_PARALLEL_TRANSITION_IDS_MUST_BE_UNIQUE")

        plans = [_to_plan(item) for item in candidates]
        admitted: list[LanePlan] = []
        for lane in sorted(plans, key=lambda item: (-item.priority, item.lane_id)):
            if self.token_bucket is not None:
                token_cost = max(1.0, lane.estimated_cost)
                if not self.token_bucket.allow(token_cost, float(now_epoch)):
                    continue
            admitted.append(lane)

        selected = self._beam_select(admitted)
        selected_ids = {item.lane_id for item in selected}
        deferred = tuple(sorted(item.lane_id for item in plans if item.lane_id not in selected_ids))
        serial = sum(item.estimated_latency_ms for item in selected)
        parallel = max((item.estimated_latency_ms for item in selected), default=0.0)
        speedup = serial / parallel if parallel > 0 else 1.0
        plan_body = {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "lanes": [_lane_payload(item) for item in selected],
            "deferred_lane_ids": deferred,
            "algorithm": ALGORITHM,
            "provider_effect_authorized": False,
            "stable_promotion_authorized": False,
        }
        return ParallelPlan(
            mission_id=mission_id,
            lanes=selected,
            deferred_lane_ids=deferred,
            estimated_parallel_latency_ms=parallel,
            estimated_serial_latency_ms=serial,
            theoretical_speedup=speedup,
            algorithm=ALGORITHM,
            plan_sha256=_canonical_hash(plan_body),
            provider_effect_authorized=False,
            stable_promotion_authorized=False,
        )

    @staticmethod
    def work_steal(
        queued: Sequence[LanePlan],
        idle_worker_ids: Sequence[str],
    ) -> dict[str, LanePlan]:
        ordered = sorted(queued, key=lambda item: (-item.priority, item.lane_id))
        assignments: dict[str, LanePlan] = {}
        used_lanes: set[str] = set()
        occupied: set[str] = set()
        for worker_id in sorted({value for value in idle_worker_ids if value}):
            for lane in ordered:
                if lane.lane_id in used_lanes:
                    continue
                if occupied.intersection(lane.conflict_domains):
                    continue
                assignments[worker_id] = lane
                used_lanes.add(lane.lane_id)
                occupied.update(lane.conflict_domains)
                break
        return assignments


class ParallelLaneExecutor:
    """Actual asyncio fan-out/fan-in for no-effect/read-only work only.

    MUTATING work is held before runner invocation. This is intentionally stricter
    than the source branch from which the primitive was harvested: post-hoc commit
    checking is not treated as a pre-effect authority control.
    """

    @staticmethod
    def _validate_plan_for_execution(plan: ParallelPlan) -> None:
        occupied: set[str] = set()
        for lane in plan.lanes:
            if lane.mutating:
                raise ParallelRuntimeError(
                    f"MUTATING_LANE_EXECUTION_HELD_BEFORE_RUNNER:{lane.lane_id}"
                )
            overlap = occupied.intersection(lane.conflict_domains)
            if overlap:
                raise ParallelRuntimeError(
                    "PARALLEL_PLAN_CONFLICT_DOMAIN_COLLISION:" + ",".join(sorted(overlap))
                )
            occupied.update(lane.conflict_domains)

    @staticmethod
    def _validate_read_result(lane_id: str, result: Mapping[str, Any]) -> None:
        if result.get("provider_effect_performed") is True:
            raise ParallelRuntimeError(
                f"READ_OR_NO_EFFECT_LANE_REPORTED_PROVIDER_MUTATION:{lane_id}"
            )

    @classmethod
    async def execute_plan(
        cls,
        plan: ParallelPlan,
        lane_runner: Callable[[LanePlan], Awaitable[Mapping[str, Any]]],
    ) -> tuple[LaneExecutionResult, ...]:
        cls._validate_plan_for_execution(plan)
        tasks: dict[str, asyncio.Task[Mapping[str, Any]]] = {}
        async with asyncio.TaskGroup() as group:
            for lane in plan.lanes:
                tasks[lane.lane_id] = group.create_task(lane_runner(lane))

        by_id = {lane.lane_id: lane for lane in plan.lanes}
        results: list[LaneExecutionResult] = []
        for lane_id in sorted(tasks):
            lane = by_id[lane_id]
            result = dict(tasks[lane_id].result())
            cls._validate_read_result(lane_id, result)
            results.append(
                LaneExecutionResult(
                    lane_id=lane_id,
                    transition_id=lane.transition_id,
                    result=result,
                )
            )
        return tuple(results)

    @staticmethod
    async def _invoke_route(
        route_id: str,
        route_runner: Callable[[str], Awaitable[Mapping[str, Any]]],
    ) -> tuple[str, Mapping[str, Any] | None, BaseException | None]:
        try:
            return route_id, dict(await route_runner(route_id)), None
        except BaseException as exc:  # route failures are evidence, not automatic global failure
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            return route_id, None, exc

    @classmethod
    async def _first_verified_from_tasks(
        cls,
        lane: LanePlan,
        tasks: Sequence[asyncio.Task[tuple[str, Mapping[str, Any] | None, BaseException | None]]],
        *,
        prior_failures: int = 0,
    ) -> Mapping[str, Any]:
        failures = int(prior_failures)
        try:
            for completed in asyncio.as_completed(tasks):
                route_id, result, error = await completed
                if error is not None:
                    failures += 1
                    continue
                assert result is not None
                cls._validate_read_result(lane.lane_id, result)
                if result.get("semantic_verified") is True and result.get("proof_valid") is True:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    return result
                failures += 1
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        raise ParallelRuntimeError(
            f"NO_SEMANTICALLY_VERIFIED_RACE_WINNER:{failures}"
        )

    @classmethod
    async def race_read_routes(
        cls,
        lane: LanePlan,
        route_ids: Sequence[str],
        route_runner: Callable[[str], Awaitable[Mapping[str, Any]]],
    ) -> Mapping[str, Any]:
        if lane.mutating:
            raise ParallelRuntimeError("SPECULATIVE_MUTATION_RACE_FORBIDDEN")
        unique = tuple(dict.fromkeys(value for value in route_ids if value))
        if len(unique) < 2:
            raise ParallelRuntimeError("READ_RACE_REQUIRES_AT_LEAST_TWO_ROUTES")
        tasks = [
            asyncio.create_task(cls._invoke_route(route_id, route_runner))
            for route_id in unique
        ]
        return await cls._first_verified_from_tasks(lane, tasks)

    @classmethod
    async def hedge_read_route(
        cls,
        lane: LanePlan,
        *,
        primary_route_id: str,
        alternate_route_ids: Sequence[str],
        hedge_after_seconds: float,
        route_runner: Callable[[str], Awaitable[Mapping[str, Any]]],
    ) -> Mapping[str, Any]:
        if lane.mutating:
            raise ParallelRuntimeError("MUTATING_LANE_HEDGE_FORBIDDEN")
        if hedge_after_seconds <= 0:
            raise ValueError("SLOS_PARALLEL_HEDGE_DELAY_MUST_BE_POSITIVE")
        if not primary_route_id:
            raise ValueError("SLOS_PARALLEL_PRIMARY_ROUTE_REQUIRED")

        alternates = tuple(
            dict.fromkeys(
                route_id
                for route_id in alternate_route_ids
                if route_id and route_id != primary_route_id
            )
        )
        primary = asyncio.create_task(cls._invoke_route(primary_route_id, route_runner))
        done, _ = await asyncio.wait({primary}, timeout=float(hedge_after_seconds))
        prior_failures = 0

        if done:
            _, result, error = primary.result()
            if error is not None:
                prior_failures += 1
            elif result is not None:
                cls._validate_read_result(lane.lane_id, result)
                if result.get("semantic_verified") is True and result.get("proof_valid") is True:
                    return result
                prior_failures += 1

        tasks: list[
            asyncio.Task[tuple[str, Mapping[str, Any] | None, BaseException | None]]
        ] = []
        if not primary.done():
            tasks.append(primary)
        tasks.extend(
            asyncio.create_task(cls._invoke_route(route_id, route_runner))
            for route_id in alternates
        )
        if not tasks:
            raise ParallelRuntimeError(
                f"NO_SEMANTICALLY_VERIFIED_HEDGE_WINNER:{prior_failures}"
            )
        return await cls._first_verified_from_tasks(
            lane,
            tasks,
            prior_failures=prior_failures,
        )


def compile_runtime_receipt(
    plan: ParallelPlan,
    results: Sequence[LaneExecutionResult],
) -> ParallelRuntimeReceipt:
    if any(lane.mutating for lane in plan.lanes):
        raise ParallelRuntimeError("MUTATING_LANE_CANNOT_RECEIVE_NO_EFFECT_RUNTIME_RECEIPT")
    provider_effect_observed = any(
        item.result.get("provider_effect_performed") is True for item in results
    )
    if provider_effect_observed:
        raise ParallelRuntimeError("PROVIDER_EFFECT_CANNOT_RECEIVE_NO_EFFECT_RUNTIME_RECEIPT")
    body = {
        "schema": SCHEMA,
        "mission_id": plan.mission_id,
        "plan_sha256": plan.plan_sha256,
        "planned_lane_count": len(plan.lanes),
        "executed_lane_count": len(results),
        "mutating_lane_executed": False,
        "provider_effect_observed": False,
        "provider_effect_authorized": False,
        "stable_promotion_authorized": False,
    }
    return ParallelRuntimeReceipt(
        **body,
        receipt_sha256=_canonical_hash(body),
    )


__all__ = [
    "ALGORITHM",
    "BoundedParallelSelector",
    "LaneCandidate",
    "LaneEffect",
    "LaneExecutionResult",
    "LanePlan",
    "ParallelLaneExecutor",
    "ParallelPlan",
    "ParallelRuntimeError",
    "ParallelRuntimeReceipt",
    "SCHEMA",
    "compile_runtime_receipt",
]
