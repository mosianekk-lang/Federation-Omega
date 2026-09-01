from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from sol_61_runtime.sol_62_frontier_primitives import ChampionChallenger, TokenBucket

from .capability_graph import CapabilityGraph, CapabilityRoute
from .mission_ir import EffectClass, MissionIR, TransitionSpec
from .provider_attestations import ProviderAttestationStore


class HyperperformanceError(RuntimeError):
    pass


@dataclass(frozen=True)
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
    mutating: bool
    reversible: bool
    conflict_domains: tuple[str, ...]
    execution_mode: str


@dataclass(frozen=True)
class ParallelPlan:
    mission_id: str
    lanes: tuple[LanePlan, ...]
    deferred_transition_ids: tuple[str, ...]
    estimated_parallel_latency_ms: float
    estimated_serial_latency_ms: float
    theoretical_speedup: float
    algorithm: str


class ParallelLaneScheduler:
    """Critical-path, VOI and empirical-route scheduler with bounded beam search.

    Hyperperformance is obtained from safe concurrency, not effect duplication:
    speculative races and straggler hedges are admitted only for READ_ONLY work.
    Mutating transitions retain one SOL transaction path and conflict-domain
    fencing. TokenBucket can cap economic/compute fan-out across planning cycles.
    """

    def __init__(
        self,
        *,
        max_lanes: int = 8,
        beam_width: int = 32,
        token_bucket: TokenBucket | None = None,
    ) -> None:
        if max_lanes < 1 or max_lanes > 64:
            raise ValueError("max_lanes must be between 1 and 64")
        if beam_width < 1 or beam_width > 512:
            raise ValueError("beam_width must be between 1 and 512")
        self.max_lanes = int(max_lanes)
        self.beam_width = int(beam_width)
        self.token_bucket = token_bucket

    @staticmethod
    def _successors(mission: MissionIR) -> dict[str, set[str]]:
        result = {item.transition_id: set() for item in mission.transitions}
        for item in mission.transitions:
            for dependency in item.dependencies:
                result[dependency].add(item.transition_id)
        return result

    @classmethod
    def critical_path_ms(cls, mission: MissionIR) -> dict[str, float]:
        nodes = mission.transition_map()
        successors = cls._successors(mission)
        memo: dict[str, float] = {}

        def visit(node_id: str) -> float:
            if node_id in memo:
                return memo[node_id]
            downstream = [visit(child) for child in successors[node_id]]
            memo[node_id] = nodes[node_id].estimated_latency_ms + (max(downstream) if downstream else 0.0)
            return memo[node_id]

        for node_id in reversed(mission.topological_order()):
            visit(node_id)
        return memo

    @staticmethod
    def _voi(item: TransitionSpec) -> float:
        # Information gained per second of latency, weighted toward early uncertainty reduction.
        return item.uncertainty_reduction / max(item.estimated_latency_ms / 1000.0, 0.001)

    @staticmethod
    def _resolve_routes(
        item: TransitionSpec,
        graph: CapabilityGraph,
        *,
        now_epoch: int,
        attestation_store: ProviderAttestationStore | None,
        authority_ceiling: str,
    ) -> tuple[tuple[CapabilityRoute, ...], int]:
        selected: list[CapabilityRoute] = []
        alternate_count = 0
        for capability in item.required_capabilities:
            candidates = graph.candidates(
                capability,
                now_epoch=now_epoch,
                attestation_store=attestation_store,
                authority_ceiling=authority_ceiling,
                allow_mutation=True,
            )
            if not candidates:
                raise HyperperformanceError(
                    f"NO_VERIFIED_ROUTE:{item.transition_id}:{capability}"
                )
            selected.append(candidates[0])
            alternate_count += max(0, len(candidates) - 1)
        return tuple(selected), alternate_count

    @classmethod
    def _candidate_lane(
        cls,
        mission: MissionIR,
        item: TransitionSpec,
        graph: CapabilityGraph,
        critical_paths: Mapping[str, float],
        *,
        now_epoch: int,
        attestation_store: ProviderAttestationStore | None,
    ) -> LanePlan:
        routes, alternate_count = cls._resolve_routes(
            item,
            graph,
            now_epoch=now_epoch,
            attestation_store=attestation_store,
            authority_ceiling=mission.authority_ceiling,
        )
        route_score = sum(route.score for route in routes) / max(len(routes), 1)
        voi = cls._voi(item)
        critical_seconds = critical_paths[item.transition_id] / 1000.0
        priority = (
            2.50 * item.expected_value
            + 1.75 * voi
            + math.log1p(critical_seconds)
            + route_score
            - 1.50 * item.risk
            - 0.20 * item.estimated_cost
        )
        route_domains = {
            domain for route in routes for domain in route.conflict_domains
        }
        domains = tuple(sorted(set(item.conflict_domains).union(route_domains)))
        speculative = (
            item.effect_class is EffectClass.READ_ONLY
            and item.speculative_allowed
            and alternate_count > 0
        )
        mode = "SPECULATIVE_READ_RACE" if speculative else "NORMAL"
        return LanePlan(
            lane_id=f"lane:{item.transition_id}",
            transition_id=item.transition_id,
            route_ids=tuple(route.capability_id for route in routes),
            priority=priority,
            critical_path_ms=critical_paths[item.transition_id],
            value_of_information=voi,
            estimated_latency_ms=item.estimated_latency_ms,
            estimated_cost=item.estimated_cost,
            risk=item.risk,
            mutating=item.mutating,
            reversible=item.reversible,
            conflict_domains=domains,
            execution_mode=mode,
        )

    def _beam_select(self, candidates: Sequence[LanePlan]) -> tuple[LanePlan, ...]:
        # State: score, lanes, occupied conflict domains, total cost.
        states: list[tuple[float, tuple[LanePlan, ...], frozenset[str], float]] = [
            (0.0, (), frozenset(), 0.0)
        ]
        for candidate in sorted(candidates, key=lambda item: (-item.priority, item.transition_id)):
            next_states = list(states)
            candidate_domains = frozenset(candidate.conflict_domains)
            for score, lanes, domains, cost in states:
                if len(lanes) >= self.max_lanes:
                    continue
                if domains.intersection(candidate_domains):
                    continue
                next_states.append(
                    (
                        score + candidate.priority,
                        lanes + (candidate,),
                        domains.union(candidate_domains),
                        cost + candidate.estimated_cost,
                    )
                )
            next_states.sort(
                key=lambda state: (
                    -state[0],
                    state[3],
                    tuple(item.transition_id for item in state[1]),
                )
            )
            states = next_states[: self.beam_width]
        best = states[0][1] if states else ()
        return tuple(sorted(best, key=lambda item: (-item.priority, item.transition_id)))

    def plan(
        self,
        mission: MissionIR,
        graph: CapabilityGraph,
        *,
        completed_transition_ids: Sequence[str] = (),
        now_epoch: int,
        attestation_store: ProviderAttestationStore | None = None,
    ) -> ParallelPlan:
        ready = mission.ready_transitions(completed_transition_ids)
        if not ready:
            return ParallelPlan(
                mission_id=mission.mission_id,
                lanes=(),
                deferred_transition_ids=(),
                estimated_parallel_latency_ms=0.0,
                estimated_serial_latency_ms=0.0,
                theoretical_speedup=1.0,
                algorithm="CP_VOI_BOUNDED_BEAM_V1",
            )
        critical_paths = self.critical_path_ms(mission)
        candidates = [
            self._candidate_lane(
                mission,
                item,
                graph,
                critical_paths,
                now_epoch=now_epoch,
                attestation_store=attestation_store,
            )
            for item in ready
        ]

        if self.token_bucket is not None:
            admitted: list[LanePlan] = []
            for lane in sorted(candidates, key=lambda item: (-item.priority, item.transition_id)):
                token_cost = max(1.0, lane.estimated_cost)
                if self.token_bucket.allow(token_cost, float(now_epoch)):
                    admitted.append(lane)
            candidates = admitted

        selected = self._beam_select(candidates)
        selected_ids = {item.transition_id for item in selected}
        deferred = tuple(sorted(item.transition_id for item in ready if item.transition_id not in selected_ids))
        serial_latency = sum(item.estimated_latency_ms for item in selected)
        parallel_latency = max((item.estimated_latency_ms for item in selected), default=0.0)
        speedup = serial_latency / parallel_latency if parallel_latency > 0 else 1.0
        return ParallelPlan(
            mission_id=mission.mission_id,
            lanes=selected,
            deferred_transition_ids=deferred,
            estimated_parallel_latency_ms=parallel_latency,
            estimated_serial_latency_ms=serial_latency,
            theoretical_speedup=speedup,
            algorithm="CP_VOI_BOUNDED_BEAM_V1",
        )

    @staticmethod
    def should_hedge(
        lane: LanePlan,
        *,
        elapsed_ms: float,
        p95_latency_ms: float,
        alternate_route_count: int,
        budget_available: bool,
    ) -> bool:
        return (
            not lane.mutating
            and lane.execution_mode in {"NORMAL", "SPECULATIVE_READ_RACE"}
            and alternate_route_count > 0
            and budget_available
            and elapsed_ms > max(p95_latency_ms, lane.estimated_latency_ms)
        )

    @staticmethod
    def work_steal(
        queued: Sequence[LanePlan],
        idle_worker_ids: Sequence[str],
    ) -> dict[str, LanePlan]:
        ordered = sorted(queued, key=lambda item: (-item.priority, item.transition_id))
        assignments: dict[str, LanePlan] = {}
        occupied: set[str] = set()
        for worker_id in sorted(set(idle_worker_ids)):
            for lane in ordered:
                if lane.transition_id in {item.transition_id for item in assignments.values()}:
                    continue
                if occupied.intersection(lane.conflict_domains):
                    continue
                assignments[worker_id] = lane
                occupied.update(lane.conflict_domains)
                break
        return assignments

    @staticmethod
    def first_semantically_verified(results: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        eligible = [
            item
            for item in results
            if item.get("semantic_verified") is True
            and item.get("proof_valid") is True
            and item.get("provider_effect_performed") is not True
        ]
        if not eligible:
            raise HyperperformanceError("NO_SEMANTICALLY_VERIFIED_RACE_WINNER")
        return min(
            eligible,
            key=lambda item: (
                float(item.get("completed_at_ms", float("inf"))),
                -float(item.get("proof_quality", 0.0)),
                str(item.get("route_id", "")),
            ),
        )

    @staticmethod
    def evaluate_challenger(
        champion_metrics: Mapping[str, float],
        challenger_metrics: Mapping[str, float],
        *,
        challenger_samples: int,
        critical_regressions: int = 0,
        min_relative_gain: float = 0.05,
    ) -> dict[str, Any]:
        return ChampionChallenger.evaluate(
            champion_metrics,
            challenger_metrics,
            min_relative_gain=min_relative_gain,
            challenger_samples=challenger_samples,
            critical_regressions=critical_regressions,
        )


__all__ = [
    "HyperperformanceError",
    "LanePlan",
    "ParallelLaneScheduler",
    "ParallelPlan",
]
