from __future__ import annotations

"""Formation Omega acceleration binding.

Composes three existing FUSE organs without creating another controller:
1. OmegaScientia for falsifiable five-minute completion planning.
2. SLOS/CodeForge engineering runtime as "Formation Ultimate Programming".
3. AlphaOmegaEngine as the build/system compiler when a workflow needs full compilation.

This module is planning/verification only. It grants no provider/effect authority.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
import importlib
import math
import sys
import tempfile
from typing import Iterable, Mapping, Sequence

from ao_harmonic_v3.science_and_routes import Hypothesis, OmegaScientia
from superior_logic.finalization_kernel import FinalizationDirective, SLOSFinalizationKernel


SCHEMA = "FUSE_FORMATION_OMEGA_ACCELERATION_BINDING_V1"
VERSION = "1.0.0"
CONTRACT_ID = "FUSE-FORMATION-OMEGA-ACCEL-001"

FIVE_MINUTE_SLO_SECONDS = 300.0
VERIFY_DELIVERY_RESERVE_SECONDS = 60.0
ACTIVE_EXECUTION_BUDGET_SECONDS = FIVE_MINUTE_SLO_SECONDS - VERIFY_DELIVERY_RESERVE_SECONDS


class DeadlineState(StrEnum):
    DEADLINE_FEASIBLE = "DEADLINE_FEASIBLE_NOT_YET_PROVEN"
    RECOMPILE_REQUIRED = "RECOMPILE_REQUIRED"
    EXTERNAL_WAIT = "EXTERNAL_WAIT_NOT_FIVE_MINUTE_GUARANTEED"
    VERIFIED = "FIVE_MINUTE_SLO_VERIFIED"
    VIOLATED = "FIVE_MINUTE_SLO_VIOLATED"


@dataclass(frozen=True, slots=True)
class TimedWorkUnit:
    unit_id: str
    objective: str
    estimated_p95_seconds: float
    depends_on: tuple[str, ...] = ()
    parallelizable: bool = False
    max_parallelism: int = 1
    mutation: bool = False
    external_wait: bool = False

    def validate(self) -> "TimedWorkUnit":
        if not self.unit_id.strip() or not self.objective.strip():
            raise ValueError("FORMATION_5M_UNIT_ID_AND_OBJECTIVE_REQUIRED")
        if self.estimated_p95_seconds < 0:
            raise ValueError("FORMATION_5M_NEGATIVE_DURATION")
        if self.max_parallelism < 1:
            raise ValueError("FORMATION_5M_PARALLELISM_INVALID")
        if self.mutation and self.max_parallelism != 1:
            raise ValueError("FORMATION_5M_MUTATION_CANNOT_INTERNAL_SHARD")
        return self


@dataclass(frozen=True, slots=True)
class ScheduledShard:
    shard_id: str
    unit_id: str
    start_seconds: float
    end_seconds: float
    lane: int


@dataclass(frozen=True, slots=True)
class DeadlineAssessment:
    state: str
    mission_id: str
    forecast_active_seconds: float | None
    forecast_total_seconds: float | None
    active_budget_seconds: float
    total_slo_seconds: float
    verification_reserve_seconds: float
    eligible_for_five_minute_slo: bool
    required_parallel_lanes: int
    shard_plan: tuple[ScheduledShard, ...]
    blocker_units: tuple[str, ...]
    recompile_actions: tuple[str, ...]
    scientia_challenge: Mapping[str, object]
    truth_boundary: str


@dataclass(frozen=True, slots=True)
class DeadlineVerification:
    mission_id: str
    state: str
    observed_wall_seconds: float
    acceptance_complete: bool
    proof_complete: bool
    within_slo: bool


@dataclass(frozen=True, slots=True)
class ProgrammingBlueprint:
    profile: str
    blueprint: Mapping[str, object]
    sophisticated_mechanisms: tuple[str, ...]
    external_effect_authorized: bool
    truth_boundary: str


@dataclass(frozen=True, slots=True)
class AlphaOmegaCompileReceipt:
    profile: str
    plan: Mapping[str, object]
    compiler_stages: tuple[str, ...]
    local_build_executed: bool
    provider_deployed: bool
    operational_verified: bool
    truth_boundary: str


class FiveMinuteScientiaGovernor:
    """Falsifiable 300-second SLO compiler for machine-executable workflows.

    The governor never pretends that arbitrary external waits can be bounded.
    It requires changed formation before execution when declared p95 work cannot
    fit inside the 240-second active budget plus 60-second proof/delivery reserve.
    """

    def __init__(self, *, max_parallel_lanes: int = 8) -> None:
        if max_parallel_lanes < 1:
            raise ValueError("FORMATION_5M_MAX_LANES_INVALID")
        self.max_parallel_lanes = int(max_parallel_lanes)
        self.scientia = OmegaScientia()

    @staticmethod
    def _validate_dag(units: Sequence[TimedWorkUnit]) -> dict[str, TimedWorkUnit]:
        rows = {u.validate().unit_id: u for u in units}
        if len(rows) != len(units):
            raise ValueError("FORMATION_5M_DUPLICATE_UNIT_ID")
        for unit in units:
            unknown = set(unit.depends_on) - set(rows)
            if unknown:
                raise ValueError(f"FORMATION_5M_UNKNOWN_DEPENDENCY:{sorted(unknown)}")
        indeg = {key: 0 for key in rows}
        graph = {key: set() for key in rows}
        for unit in units:
            for dep in unit.depends_on:
                graph[dep].add(unit.unit_id)
                indeg[unit.unit_id] += 1
        ready = sorted(k for k, v in indeg.items() if v == 0)
        seen: list[str] = []
        while ready:
            node = ready.pop(0)
            seen.append(node)
            for nxt in sorted(graph[node]):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
                    ready.sort()
        if len(seen) != len(rows):
            raise ValueError("FORMATION_5M_DEPENDENCY_CYCLE")
        return rows

    @staticmethod
    def _shards(unit: TimedWorkUnit, *, active_budget: float) -> tuple[tuple[str, float], ...]:
        if unit.external_wait:
            return ()
        if not unit.parallelizable or unit.mutation:
            count = 1
        else:
            target = max(30.0, min(120.0, active_budget / 2.0))
            count = min(unit.max_parallelism, max(1, math.ceil(unit.estimated_p95_seconds / target)))
        duration = unit.estimated_p95_seconds / count if count else 0.0
        overhead = 5.0 if count > 1 else 0.0
        return tuple((f"{unit.unit_id}#{i+1}", duration + overhead) for i in range(count))

    def _schedule(self, units: Sequence[TimedWorkUnit]) -> tuple[tuple[ScheduledShard, ...], float, int]:
        rows = self._validate_dag(units)
        unit_shards = {
            unit.unit_id: self._shards(unit, active_budget=ACTIVE_EXECUTION_BUDGET_SECONDS)
            for unit in units
        }

        completed_unit_at: dict[str, float] = {}
        unscheduled = set(rows)
        lane_available = [0.0 for _ in range(self.max_parallel_lanes)]
        scheduled: list[ScheduledShard] = []

        while unscheduled:
            progress = False
            for unit_id in sorted(tuple(unscheduled)):
                unit = rows[unit_id]
                if any(dep not in completed_unit_at for dep in unit.depends_on):
                    continue
                dep_ready = max((completed_unit_at[d] for d in unit.depends_on), default=0.0)
                shards = unit_shards[unit_id]
                if not shards:
                    completed_unit_at[unit_id] = dep_ready
                    unscheduled.remove(unit_id)
                    progress = True
                    break

                ends: list[float] = []
                for shard_id, duration in shards:
                    lane = min(range(len(lane_available)), key=lambda idx: (max(lane_available[idx], dep_ready), idx))
                    start = max(lane_available[lane], dep_ready)
                    end = start + duration
                    lane_available[lane] = end
                    scheduled.append(ScheduledShard(shard_id, unit_id, start, end, lane))
                    ends.append(end)
                completed_unit_at[unit_id] = max(ends)
                unscheduled.remove(unit_id)
                progress = True
                break
            if not progress:
                raise ValueError("FORMATION_5M_SCHEDULER_STALLED")

        active = max((x.end_seconds for x in scheduled), default=0.0)
        used_lanes = 0 if not scheduled else 1 + max(x.lane for x in scheduled)
        return tuple(sorted(scheduled, key=lambda x: (x.start_seconds, x.lane, x.shard_id))), active, used_lanes

    def assess(self, *, mission_id: str, units: Sequence[TimedWorkUnit]) -> DeadlineAssessment:
        if not mission_id.strip() or not units:
            raise ValueError("FORMATION_5M_MISSION_AND_UNITS_REQUIRED")
        external = tuple(sorted(u.unit_id for u in units if u.external_wait))
        shard_plan, active, used_lanes = self._schedule(units)
        total = active + VERIFY_DELIVERY_RESERVE_SECONDS
        contradictions: list[str] = []
        if external:
            contradictions.append("One or more units depend on external wait time not controlled by FUSE.")
        if active > ACTIVE_EXECUTION_BUDGET_SECONDS:
            contradictions.append(
                f"Declared p95 active critical path {active:.3f}s exceeds {ACTIVE_EXECUTION_BUDGET_SECONDS:.0f}s."
            )

        hypothesis = Hypothesis(
            hypothesis_id=f"{mission_id}:FIVE_MINUTE_TERMINALITY",
            statement=f"{mission_id} can reach verified owner-facing completion within 300 seconds.",
            supporting_observations=[
                f"scheduled_active_p95_seconds={active:.3f}",
                f"verification_delivery_reserve_seconds={VERIFY_DELIVERY_RESERVE_SECONDS:.0f}",
                f"parallel_lanes_used={used_lanes}",
            ],
            conflicting_observations=contradictions,
            predicted_evidence=[
                "Observed wall clock from accepted mission to verified terminal delivery is <=300 seconds.",
                "All acceptance predicates and required proof are complete at delivery.",
            ],
            falsifiers=[
                "Observed wall clock exceeds 300 seconds.",
                "Any required proof or acceptance predicate remains open at 300 seconds.",
                "An undeclared external wait or serialization dependency enters the critical path.",
            ],
            confidence=1.0 if not contradictions else 0.0,
        )
        challenge = self.scientia.challenge(hypothesis)

        if external:
            state = DeadlineState.EXTERNAL_WAIT
            eligible = False
            blockers = external
        elif active > ACTIVE_EXECUTION_BUDGET_SECONDS:
            state = DeadlineState.RECOMPILE_REQUIRED
            eligible = False
            blockers = tuple(
                sorted(
                    u.unit_id
                    for u in units
                    if (not u.parallelizable and u.estimated_p95_seconds > ACTIVE_EXECUTION_BUDGET_SECONDS / 2)
                    or (u.parallelizable and u.max_parallelism <= 1 and u.estimated_p95_seconds > ACTIVE_EXECUTION_BUDGET_SECONDS / 2)
                )
            )
        else:
            state = DeadlineState.DEADLINE_FEASIBLE
            eligible = True
            blockers = ()

        actions: list[str] = []
        if state is DeadlineState.RECOMPILE_REQUIRED:
            actions.extend(
                (
                    "REUSE_OR_PREWARM_EXPENSIVE_PREREQUISITES",
                    "DECOMPOSE_TO_DISJOINT_PARALLEL_LANES",
                    "MOVE_COMPUTE_TO_DATA_OR_FASTER_QUALIFIED_SURFACE",
                    "RACE_ONLY_INDEPENDENT_HIGH_VALUE_CANDIDATES",
                    "BUILD_MINIMUM_RESIDUAL_FOR_PERSISTENT_BOTTLENECK",
                    "REESTIMATE_P95_AND_RECOMPILE_BEFORE_EXECUTION",
                )
            )
        elif state is DeadlineState.EXTERNAL_WAIT:
            actions.extend(
                (
                    "SPLIT_ACTIVE_COMPUTE_FROM_EXTERNAL_WAIT",
                    "COMPLETE_ALL_MACHINE_PREREQUISITES_WITHIN_ACTIVE_BUDGET",
                    "PERSIST_CHECKPOINT_AND_RESUME_ON_EVENT",
                    "DO_NOT_CLAIM_FIVE_MINUTE_FULL_COMPLETION_UNTIL_EXTERNAL_WAIT_IS_BOUNDED",
                )
            )

        return DeadlineAssessment(
            state=state.value,
            mission_id=mission_id,
            forecast_active_seconds=round(active, 3),
            forecast_total_seconds=round(total, 3),
            active_budget_seconds=ACTIVE_EXECUTION_BUDGET_SECONDS,
            total_slo_seconds=FIVE_MINUTE_SLO_SECONDS,
            verification_reserve_seconds=VERIFY_DELIVERY_RESERVE_SECONDS,
            eligible_for_five_minute_slo=eligible,
            required_parallel_lanes=used_lanes,
            shard_plan=shard_plan,
            blocker_units=blockers,
            recompile_actions=tuple(actions),
            scientia_challenge=challenge,
            truth_boundary=(
                "DEADLINE_FORECAST!=WORKFLOW_EXECUTED!=OBSERVED_WALL_CLOCK"
                "!=ACCEPTANCE_COMPLETE!=PROOF_COMPLETE!=FIVE_MINUTE_SLO_VERIFIED"
            ),
        )

    @staticmethod
    def verify_observed(
        *,
        mission_id: str,
        observed_wall_seconds: float,
        acceptance_complete: bool,
        proof_complete: bool,
    ) -> DeadlineVerification:
        if observed_wall_seconds < 0:
            raise ValueError("FORMATION_5M_OBSERVED_DURATION_INVALID")
        within = observed_wall_seconds <= FIVE_MINUTE_SLO_SECONDS
        state = (
            DeadlineState.VERIFIED
            if within and acceptance_complete and proof_complete
            else DeadlineState.VIOLATED
        )
        return DeadlineVerification(
            mission_id=mission_id,
            state=state.value,
            observed_wall_seconds=float(observed_wall_seconds),
            acceptance_complete=bool(acceptance_complete),
            proof_complete=bool(proof_complete),
            within_slo=within,
        )


class FormationUltimateProgramming:
    """Profile over the existing SLOS engineering runtime; not a new programming engine."""

    PROFILE = "FORMATION_ULTIMATE_PROGRAMMING_V1"

    def compile(
        self,
        *,
        mission_id: str,
        base_revision: str,
        objective: str,
        required_capabilities: Iterable[str],
        repository_files: Mapping[str, str],
        toolchain: Mapping[str, str],
        dependencies: Mapping[str, str],
        risk: str = "HIGH",
    ) -> ProgrammingBlueprint:
        directive = FinalizationDirective(
            mission_id=mission_id,
            base_revision=base_revision,
            objective=objective,
            required_capabilities=tuple(sorted(set(required_capabilities))),
            risk=risk,
            external_effects=False,
            authority_ready=True,
            independent_verification_required=True,
        )
        blueprint = SLOSFinalizationKernel().compile(
            directive,
            repository_files=repository_files,
            toolchain=toolchain,
            dependencies=dependencies,
        )
        return ProgrammingBlueprint(
            profile=self.PROFILE,
            blueprint=asdict(blueprint),
            sophisticated_mechanisms=(
                "REPOGRAPH_IMPACT_ANALYSIS",
                "ARCHITECTURE_GENOME",
                "CONTEXT_TOURNAMENT",
                "HARNESS_TOURNAMENT",
                "PREPARED_WORKSPACE_FORGE",
                "CONFLICT_SAFE_CODING_FLEET",
                "VERIFICATION_SUPERCOURT",
                "AUTONOMOUS_CAPABILITY_CLOSURE",
                "EVOLUTION_LAB",
                "ACCEPTANCE_INTEGRITY",
                "SKILLFORGE_V2",
            ),
            external_effect_authorized=False,
            truth_boundary=(
                "PROGRAMMING_BLUEPRINT_COMPILED!=CODE_MUTATED!=TESTS_EXECUTED"
                "!=SOURCE_ADMITTED!=RUNTIME_DEPLOYED!=OWNER_VALUE_VERIFIED"
            ),
        )


class FormationAlphaOmegaCompiler:
    """Planning bridge to the existing AlphaOmegaEngine."""

    PROFILE = "FORMATION_ALPHA_OMEGA_COMPILER_V1"

    @staticmethod
    def _source_root(repo_root: Path) -> Path:
        return repo_root / "systems" / "alpha-omega-turnkey" / "src"

    def compile(
        self,
        *,
        mission_id: str,
        objective: str,
        outcomes: Iterable[str] = (),
        constraints: Iterable[str] = (),
        preferred_surfaces: Iterable[str] = (),
        repo_root: str | Path | None = None,
    ) -> AlphaOmegaCompileReceipt:
        root = Path(repo_root or Path(__file__).resolve().parents[1])
        source_root = self._source_root(root)
        if not source_root.exists():
            raise RuntimeError("ALPHA_OMEGA_CANONICAL_SOURCE_MISSING")
        source_text = str(source_root)
        inserted = False
        if source_text not in sys.path:
            sys.path.insert(0, source_text)
            inserted = True
        try:
            alpha_module = importlib.import_module("alpha_omega")
            engine_cls = getattr(alpha_module, "AlphaOmegaEngine")
            with tempfile.TemporaryDirectory(prefix="fuse-alpha-omega-plan-") as tmp:
                engine = engine_cls(tmp)
                plan = engine.build_plan(
                    {
                        "title": mission_id,
                        "description": objective,
                        "users": ["FUSE owner"],
                        "outcomes": list(outcomes),
                        "constraints": list(constraints),
                        "preferred_surfaces": list(preferred_surfaces),
                    }
                )
                plan_dict = plan.to_dict()
        finally:
            if inserted:
                try:
                    sys.path.remove(source_text)
                except ValueError:
                    pass

        return AlphaOmegaCompileReceipt(
            profile=self.PROFILE,
            plan=plan_dict,
            compiler_stages=(
                "DISCOVERY",
                "DECOMPOSITION",
                "ARCHITECTURE",
                "BUILD",
                "TEST",
                "DEPLOY",
                "VERIFY",
                "OPERATE",
                "MAINTAIN",
            ),
            local_build_executed=False,
            provider_deployed=False,
            operational_verified=False,
            truth_boundary=(
                "ALPHA_OMEGA_PLAN_COMPILED!=ARTIFACTS_BUILT!=PROVIDER_DEPLOYED"
                "!=OPERATIONAL_VERIFIED!=COMPLETE"
            ),
        )


__all__ = [
    "ACTIVE_EXECUTION_BUDGET_SECONDS",
    "AlphaOmegaCompileReceipt",
    "DeadlineAssessment",
    "DeadlineState",
    "DeadlineVerification",
    "FIVE_MINUTE_SLO_SECONDS",
    "FiveMinuteScientiaGovernor",
    "FormationAlphaOmegaCompiler",
    "FormationUltimateProgramming",
    "ProgrammingBlueprint",
    "TimedWorkUnit",
]
