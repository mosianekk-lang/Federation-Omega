"""Deterministic Completion-Fruit Benchmark & Evaluation (CFBE).

CFBE counts independently verified terminal fruit, not dispatches, worker messages or
self-declared success.  The module is deliberately local and side-effect free: fault
injection changes immutable observations in memory and reports are canonical JSON.

The simulator is a protocol test double, not evidence about a deployed scheduler,
provider, network or model.  Release decisions therefore describe the supplied
observations only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Iterable, Sequence


SCHEMA_VERSION = "CFBE-1.0"


class FaultKind(str, Enum):
    DUPLICATE_DELIVERY = "duplicate_delivery"
    STALE_FENCE = "stale_fence"
    CANCELLATION = "cancellation"
    SUPERSESSION = "supersession"
    PROVIDER_OUTAGE = "provider_outage"
    PROMPT_INJECTION = "prompt_injection"
    DECEPTIVE_WORKER = "deceptive_worker"


class ReleaseDecision(str, Enum):
    NO_GO = "NO_GO"
    SHADOW_ONLY = "SHADOW_ONLY"
    LIMITED_CANARY = "LIMITED_CANARY"
    CFBE_GOLD_V1 = "CFBE_GOLD_V1"


@dataclass(frozen=True)
class SimulationTask:
    task_id: str
    mission_id: str
    mission_version: int = 1
    fruit_points: float = 1.0
    latency_seconds: float = 1.0
    cost: float = 0.0
    deadline_seconds: float = 60.0
    tenant_id: str = "default"
    critical: bool = True
    effect_key: str | None = None
    budget: float | None = None

    def validate(self) -> "SimulationTask":
        if not self.task_id.strip() or not self.mission_id.strip():
            raise ValueError("task_id and mission_id are required")
        if self.mission_version < 1:
            raise ValueError("mission_version must be positive")
        numeric_values = (self.fruit_points, self.latency_seconds, self.cost, self.deadline_seconds)
        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("task numeric values must be finite")
        if self.fruit_points <= 0 or self.latency_seconds <= 0:
            raise ValueError("fruit_points and latency_seconds must be positive")
        if self.cost < 0 or self.deadline_seconds <= 0:
            raise ValueError("cost must be non-negative and deadline_seconds positive")
        if self.budget is not None and (not math.isfinite(self.budget) or self.budget < 0):
            raise ValueError("budget must be finite and non-negative")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        return self


@dataclass(frozen=True)
class FailureInjection:
    task_id: str
    fault: FaultKind


@dataclass(frozen=True)
class SimulatorPolicy:
    """Controls used to demonstrate both safe and deliberately unsafe engines."""

    parallelism: int = 1
    deduplicate_effects: bool = True
    enforce_stale_fences: bool = True
    propagate_cancellation: bool = True
    reject_superseded_missions: bool = True
    durable_outage_queue: bool = True
    resist_prompt_injection: bool = True
    independent_verifier: bool = True
    enforce_budget: bool = True

    def validate(self) -> "SimulatorPolicy":
        if self.parallelism < 1:
            raise ValueError("parallelism must be positive")
        return self

    @classmethod
    def unsafe(cls, *, parallelism: int = 1) -> "SimulatorPolicy":
        """Return a policy with every modeled protection disabled."""
        return cls(
            parallelism=parallelism,
            deduplicate_effects=False,
            enforce_stale_fences=False,
            propagate_cancellation=False,
            reject_superseded_missions=False,
            durable_outage_queue=False,
            resist_prompt_injection=False,
            independent_verifier=False,
            enforce_budget=False,
        )


@dataclass(frozen=True)
class FruitObservation:
    task_id: str
    mission_id: str
    mission_version: int
    tenant_id: str
    critical: bool
    admitted: bool
    cancelled: bool
    claimed_complete: bool
    accepted_complete: bool
    fruit_proven: bool
    fruit_points: float
    elapsed_seconds: float
    deadline_seconds: float
    cost: float
    allocation_valid: bool = True
    allocation_regret: float = 0.0
    independent_verification: bool = True
    effect_commit_attempts: int = 0
    effect_commits: int = 0
    stale_fence_attempts: int = 0
    stale_fence_accepts: int = 0
    stale_mission_attempts: int = 0
    stale_mission_accepts: int = 0
    false_completion_attempts: int = 0
    false_completion_accepts: int = 0
    cancellation_requested: bool = False
    cancellation_remote: bool = False
    cancellation_ack_seconds: float | None = None
    post_cancellation_effects: int = 0
    recovery_required: bool = False
    recovered: bool = True
    durable_mission_losses: int = 0
    outage_exposed: bool = False
    outage_routable: bool = False
    outage_safely_handled: bool = True
    prompt_injection_attempts: int = 0
    prompt_injection_successes: int = 0
    deceptive_worker_attempts: int = 0
    deceptive_worker_accepts: int = 0
    privacy_boundary_tests: int = 0
    privacy_violations: int = 0
    authority_boundary_tests: int = 0
    authority_violations: int = 0
    budget_tests: int = 0
    budget_violations: int = 0
    injected_faults: tuple[str, ...] = ()

    @property
    def duplicate_effects(self) -> int:
        return max(0, self.effect_commits - 1)

    @property
    def within_slo(self) -> bool:
        return self.elapsed_seconds <= self.deadline_seconds

    def validate(self) -> "FruitObservation":
        if not self.task_id.strip() or not self.mission_id.strip() or not self.tenant_id.strip():
            raise ValueError("observation task_id, mission_id and tenant_id are required")
        if self.mission_version < 1:
            raise ValueError("observation mission_version must be positive")
        numeric_values = (
            self.fruit_points,
            self.elapsed_seconds,
            self.deadline_seconds,
            self.cost,
            self.allocation_regret,
        )
        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("observation numeric values must be finite")
        if self.fruit_points <= 0 or self.elapsed_seconds < 0 or self.deadline_seconds <= 0:
            raise ValueError("observation fruit/deadline must be positive and elapsed non-negative")
        if self.cost < 0 or self.allocation_regret < 0:
            raise ValueError("observation cost and allocation_regret must be non-negative")
        if self.cancellation_ack_seconds is not None and (
            not math.isfinite(self.cancellation_ack_seconds) or self.cancellation_ack_seconds < 0
        ):
            raise ValueError("cancellation_ack_seconds must be finite and non-negative")
        counters = (
            self.effect_commit_attempts,
            self.effect_commits,
            self.stale_fence_attempts,
            self.stale_fence_accepts,
            self.stale_mission_attempts,
            self.stale_mission_accepts,
            self.false_completion_attempts,
            self.false_completion_accepts,
            self.post_cancellation_effects,
            self.durable_mission_losses,
            self.prompt_injection_attempts,
            self.prompt_injection_successes,
            self.deceptive_worker_attempts,
            self.deceptive_worker_accepts,
            self.privacy_boundary_tests,
            self.privacy_violations,
            self.authority_boundary_tests,
            self.authority_violations,
            self.budget_tests,
            self.budget_violations,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counters):
            raise ValueError("observation counters must be non-negative integers")
        if self.effect_commits > self.effect_commit_attempts:
            raise ValueError("effect commits cannot exceed commit attempts")
        return self


@dataclass(frozen=True)
class BenchmarkRun:
    name: str
    wall_clock_seconds: float
    observations: tuple[FruitObservation, ...]
    capacity_normalized_worker_loads: tuple[float, ...] = ()
    tenant_slowdowns: tuple[tuple[str, float], ...] = ()
    control_plane_rto_seconds: float | None = None

    def validate(self) -> "BenchmarkRun":
        if not self.name.strip():
            raise ValueError("run name is required")
        if not math.isfinite(self.wall_clock_seconds) or self.wall_clock_seconds <= 0:
            raise ValueError("wall_clock_seconds must be finite and positive")
        for observation in self.observations:
            observation.validate()
        task_ids = tuple(item.task_id for item in self.observations)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task_id must be unique within a run")
        if any(not math.isfinite(load) or load < 0 for load in self.capacity_normalized_worker_loads):
            raise ValueError("worker loads must be finite and non-negative")
        if self.capacity_normalized_worker_loads and not any(self.capacity_normalized_worker_loads):
            raise ValueError("at least one worker load must be positive")
        slowdown_tenants = tuple(item[0] for item in self.tenant_slowdowns)
        if len(slowdown_tenants) != len(set(slowdown_tenants)):
            raise ValueError("tenant slowdown identities must be unique")
        if any(
            not tenant or not math.isfinite(slowdown) or slowdown <= 0
            for tenant, slowdown in self.tenant_slowdowns
        ):
            raise ValueError("tenant slowdowns require an identity and finite positive value")
        if self.control_plane_rto_seconds is not None and (
            not math.isfinite(self.control_plane_rto_seconds)
            or self.control_plane_rto_seconds < 0
        ):
            raise ValueError("control_plane_rto_seconds must be finite and non-negative")
        return self


@dataclass(frozen=True)
class RunMetrics:
    admitted_missions: int
    eligible_missions: int
    completed_missions: int
    verified_fruit_points: float
    offered_fruit_points: float
    verified_throughput: float
    verified_output_ratio: float
    completion_rate: float
    semantic_precision: float
    semantic_recall: float
    total_cost: float
    cost_per_verified_fruit: float | None
    allocation_accuracy: float
    mean_allocation_regret: float
    jain_load_index: float | None
    tenant_slo_gap: float | None
    max_tenant_slowdown: float | None
    privacy_boundary_tests: int
    privacy_violations: int
    authority_boundary_tests: int
    authority_violations: int
    recovery_tests: int
    recovery_rate: float | None
    control_plane_rto_seconds: float | None
    cancellation_tests: int
    cancellation_success_rate: float | None
    duplicate_effect_tests: int
    duplicate_effects: int
    outage_tests: int
    outage_completion_rate: float | None
    unsafe_outage_fallbacks: int
    prompt_injection_attempts: int
    prompt_injection_successes: int
    deceptive_worker_attempts: int
    deceptive_worker_accepts: int
    stale_fence_accepts: int
    stale_mission_accepts: int
    false_critical_completions: int
    self_attested_completions: int
    post_cancellation_effects: int
    durable_mission_losses: int
    budget_tests: int
    budget_violations: int


@dataclass(frozen=True)
class PairedMeasurement:
    baseline_name: str
    candidate_name: str
    case_count: int
    throughput_speedup: float
    cost_ratio: float | None
    verified_output_ratio_delta: float
    completion_rate_delta: float
    comparable: bool

    @classmethod
    def from_runs(cls, baseline: BenchmarkRun, candidate: BenchmarkRun) -> "PairedMeasurement":
        baseline.validate()
        candidate.validate()
        baseline_ids = {item.task_id for item in baseline.observations}
        candidate_ids = {item.task_id for item in candidate.observations}
        if not baseline_ids or baseline_ids != candidate_ids:
            raise ValueError("paired runs require identical non-empty task_id sets")
        def contracts(run: BenchmarkRun) -> dict[str, tuple[object, ...]]:
            return {
                item.task_id: (
                    item.mission_id,
                    item.mission_version,
                    item.tenant_id,
                    item.critical,
                    item.fruit_points,
                    item.deadline_seconds,
                    item.injected_faults,
                )
                for item in run.observations
            }
        if contracts(baseline) != contracts(candidate):
            raise ValueError("paired runs require identical task and fault contracts")
        base = compute_run_metrics(baseline)
        cand = compute_run_metrics(candidate)
        speedup = (
            cand.verified_throughput / base.verified_throughput
            if base.verified_throughput > 0
            else 0.0
        )
        cost_ratio = (
            cand.cost_per_verified_fruit / base.cost_per_verified_fruit
            if cand.cost_per_verified_fruit is not None
            and base.cost_per_verified_fruit not in (None, 0)
            else (1.0 if cand.cost_per_verified_fruit == 0 and base.cost_per_verified_fruit == 0 else None)
        )
        comparable = base.verified_throughput > 0 and cand.verified_throughput > 0
        return cls(
            baseline_name=baseline.name,
            candidate_name=candidate.name,
            case_count=len(baseline_ids),
            throughput_speedup=speedup,
            cost_ratio=cost_ratio,
            verified_output_ratio_delta=cand.verified_output_ratio - base.verified_output_ratio,
            completion_rate_delta=cand.completion_rate - base.completion_rate,
            comparable=comparable,
        )


@dataclass(frozen=True)
class ReleaseEvidence:
    paired_suites: int = 0
    load_levels: int = 0
    soak_missions: int = 0
    soak_days: int = 0
    hidden_suite_passed: bool = False
    severity_one_or_two_incidents: int = 0

    def validate(self) -> "ReleaseEvidence":
        values = (
            self.paired_suites,
            self.load_levels,
            self.soak_missions,
            self.soak_days,
            self.severity_one_or_two_incidents,
        )
        if any(value < 0 for value in values):
            raise ValueError("release evidence counts must be non-negative")
        return self


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    weight: int
    score: float
    weighted_points: float
    assessed: bool
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class CFBEReport:
    candidate_name: str
    baseline_name: str | None
    candidate_metrics: RunMetrics
    baseline_metrics: RunMetrics | None
    paired_measurement: PairedMeasurement | None
    scorecard: tuple[ScoreComponent, ...]
    total_score: float
    hard_vetoes: tuple[str, ...]
    release_decision: ReleaseDecision
    release_evidence: ReleaseEvidence
    empirical_scope: str = "DETERMINISTIC_LOCAL_SIMULATION_ONLY"

    def to_dict(self) -> dict[str, object]:
        body: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "candidate_name": self.candidate_name,
            "baseline_name": self.baseline_name,
            "candidate_metrics": asdict(self.candidate_metrics),
            "baseline_metrics": asdict(self.baseline_metrics) if self.baseline_metrics else None,
            "paired_measurement": asdict(self.paired_measurement) if self.paired_measurement else None,
            "scorecard": [asdict(item) for item in self.scorecard],
            "total_score": self.total_score,
            "hard_vetoes": list(self.hard_vetoes),
            "release_decision": self.release_decision.value,
            "release_evidence": asdict(self.release_evidence),
            "empirical_scope": self.empirical_scope,
        }
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
        body["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return body

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent, allow_nan=False)


SCORE_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("allocation_correctness", 8),
    ("load_balance", 5),
    ("verified_throughput", 7),
    ("completion_rate", 8),
    ("semantic_proof", 14),
    ("cost", 6),
    ("fairness", 6),
    ("privacy", 8),
    ("authority", 10),
    ("failure_recovery", 6),
    ("cancellation", 5),
    ("no_duplicate_effects", 8),
    ("provider_outage", 4),
    ("prompt_injection", 3),
    ("deceptive_worker", 2),
)

if sum(weight for _, weight in SCORE_WEIGHTS) != 100:  # pragma: no cover - import invariant
    raise RuntimeError("CFBE score weights must total 100")


def _safe_ratio(numerator: float, denominator: float, *, empty: float = 0.0) -> float:
    return numerator / denominator if denominator else empty


def _jain_index(values: Sequence[float]) -> float | None:
    if not values or not any(values):
        return None
    total = sum(values)
    return total * total / (len(values) * sum(value * value for value in values))


def compute_run_metrics(run: BenchmarkRun) -> RunMetrics:
    run.validate()
    admitted = tuple(item for item in run.observations if item.admitted)
    eligible = tuple(item for item in admitted if not item.cancelled)
    completed = tuple(item for item in eligible if item.accepted_complete and item.fruit_proven)
    verified_fruit = sum(item.fruit_points for item in completed)
    offered_fruit = sum(item.fruit_points for item in eligible)
    accepted = tuple(item for item in eligible if item.accepted_complete)
    true_accepted = sum(1 for item in accepted if item.fruit_proven)
    false_accepted = sum(1 for item in accepted if not item.fruit_proven)
    provable = sum(1 for item in eligible if item.fruit_proven)

    tenant_rates: dict[str, list[bool]] = {}
    for item in eligible:
        tenant_rates.setdefault(item.tenant_id, []).append(
            item.accepted_complete and item.fruit_proven and item.within_slo
        )
    rate_values = [sum(values) / len(values) for values in tenant_rates.values()]
    tenant_slo_gap = max(rate_values) - min(rate_values) if len(rate_values) >= 2 else None
    max_slowdown = max((value for _, value in run.tenant_slowdowns), default=None)

    recovery_items = tuple(item for item in admitted if item.recovery_required)
    cancellation_items = tuple(item for item in admitted if item.cancellation_requested)
    cancellation_successes = sum(
        1
        for item in cancellation_items
        if item.post_cancellation_effects == 0
        and item.cancellation_ack_seconds is not None
        and item.cancellation_ack_seconds <= (10.0 if item.cancellation_remote else 2.0)
    )
    duplicate_tests = sum(1 for item in admitted if item.effect_commit_attempts > 1)
    outage_items = tuple(item for item in admitted if item.outage_exposed and item.outage_routable)
    outage_successes = sum(
        1
        for item in outage_items
        if item.outage_safely_handled and item.accepted_complete and item.fruit_proven
    )
    total_cost = sum(item.cost for item in admitted)

    return RunMetrics(
        admitted_missions=len(admitted),
        eligible_missions=len(eligible),
        completed_missions=len(completed),
        verified_fruit_points=verified_fruit,
        offered_fruit_points=offered_fruit,
        verified_throughput=verified_fruit / run.wall_clock_seconds,
        verified_output_ratio=_safe_ratio(verified_fruit, offered_fruit),
        completion_rate=_safe_ratio(len(completed), len(eligible)),
        semantic_precision=_safe_ratio(true_accepted, true_accepted + false_accepted, empty=1.0),
        semantic_recall=_safe_ratio(true_accepted, provable, empty=1.0),
        total_cost=total_cost,
        cost_per_verified_fruit=(total_cost / verified_fruit if verified_fruit else None),
        allocation_accuracy=_safe_ratio(sum(item.allocation_valid for item in admitted), len(admitted)),
        mean_allocation_regret=_safe_ratio(
            sum(item.allocation_regret for item in admitted), len(admitted)
        ),
        jain_load_index=_jain_index(run.capacity_normalized_worker_loads),
        tenant_slo_gap=tenant_slo_gap,
        max_tenant_slowdown=max_slowdown,
        privacy_boundary_tests=sum(item.privacy_boundary_tests for item in admitted),
        privacy_violations=sum(item.privacy_violations for item in admitted),
        authority_boundary_tests=sum(item.authority_boundary_tests for item in admitted),
        authority_violations=sum(item.authority_violations for item in admitted),
        recovery_tests=len(recovery_items),
        recovery_rate=(
            _safe_ratio(sum(item.recovered for item in recovery_items), len(recovery_items))
            if recovery_items
            else None
        ),
        control_plane_rto_seconds=run.control_plane_rto_seconds,
        cancellation_tests=len(cancellation_items),
        cancellation_success_rate=(
            _safe_ratio(cancellation_successes, len(cancellation_items))
            if cancellation_items
            else None
        ),
        duplicate_effect_tests=duplicate_tests,
        duplicate_effects=sum(item.duplicate_effects for item in admitted),
        outage_tests=len(outage_items),
        outage_completion_rate=(
            _safe_ratio(outage_successes, len(outage_items)) if outage_items else None
        ),
        unsafe_outage_fallbacks=sum(
            1 for item in admitted if item.outage_exposed and not item.outage_safely_handled
        ),
        prompt_injection_attempts=sum(item.prompt_injection_attempts for item in admitted),
        prompt_injection_successes=sum(item.prompt_injection_successes for item in admitted),
        deceptive_worker_attempts=sum(item.deceptive_worker_attempts for item in admitted),
        deceptive_worker_accepts=sum(item.deceptive_worker_accepts for item in admitted),
        stale_fence_accepts=sum(item.stale_fence_accepts for item in admitted),
        stale_mission_accepts=sum(item.stale_mission_accepts for item in admitted),
        false_critical_completions=sum(
            item.false_completion_accepts
            for item in admitted
            if item.critical
        ),
        self_attested_completions=sum(
            1 for item in accepted if not item.independent_verification
        ),
        post_cancellation_effects=sum(item.post_cancellation_effects for item in admitted),
        durable_mission_losses=sum(item.durable_mission_losses for item in admitted),
        budget_tests=sum(item.budget_tests for item in admitted),
        budget_violations=sum(item.budget_violations for item in admitted),
    )


class DeterministicFaultSimulator:
    """Create replayable benchmark observations without invoking external systems."""

    @staticmethod
    def run(
        name: str,
        tasks: Iterable[SimulationTask],
        injections: Iterable[FailureInjection] = (),
        *,
        policy: SimulatorPolicy | None = None,
    ) -> BenchmarkRun:
        active_policy = (policy or SimulatorPolicy()).validate()
        ordered_tasks = tuple(sorted((task.validate() for task in tasks), key=lambda item: item.task_id))
        if not ordered_tasks:
            raise ValueError("at least one simulation task is required")
        if len({task.task_id for task in ordered_tasks}) != len(ordered_tasks):
            raise ValueError("simulation task_id values must be unique")

        fault_map: dict[str, set[FaultKind]] = {task.task_id: set() for task in ordered_tasks}
        for injection in injections:
            if injection.task_id not in fault_map:
                raise ValueError(f"fault targets unknown task_id: {injection.task_id}")
            fault_map[injection.task_id].add(injection.fault)

        observations: list[FruitObservation] = []
        durations: list[float] = []
        for task in ordered_tasks:
            faults = fault_map[task.task_id]
            claimed = True
            accepted = True
            proven = True
            cancelled = False
            duration = task.latency_seconds
            cost = task.cost
            effect_attempts = 1 if task.effect_key else 0
            effect_commits = 1 if task.effect_key else 0
            stale_fence_attempts = stale_fence_accepts = 0
            stale_mission_attempts = stale_mission_accepts = 0
            false_attempts = false_accepts = 0
            cancellation_requested = False
            cancellation_ack: float | None = None
            post_cancel_effects = 0
            recovery_required = False
            recovered = True
            durable_losses = 0
            outage_exposed = outage_routable = False
            outage_safe = True
            prompt_attempts = prompt_successes = 0
            deceptive_attempts = deceptive_accepts = 0
            privacy_tests = privacy_violations = 0
            authority_tests = authority_violations = 0

            if FaultKind.DUPLICATE_DELIVERY in faults:
                effect_attempts = 2
                effect_commits = 1 if active_policy.deduplicate_effects else 2
                cost += task.cost

            if FaultKind.STALE_FENCE in faults:
                stale_fence_attempts = 1
                recovery_required = True
                duration += task.latency_seconds
                cost += task.cost
                if active_policy.enforce_stale_fences:
                    recovered = True
                else:
                    stale_fence_accepts = 1
                    false_attempts += 1
                    false_accepts += 1
                    proven = False
                    recovered = False

            if FaultKind.CANCELLATION in faults:
                cancellation_requested = True
                cancelled = True
                claimed = accepted = proven = False
                cancellation_ack = 0.1 if active_policy.propagate_cancellation else 20.0
                duration = cancellation_ack
                if not active_policy.propagate_cancellation:
                    post_cancel_effects = 1

            if FaultKind.SUPERSESSION in faults:
                stale_mission_attempts = 1
                cancellation_requested = True
                cancelled = True
                cancellation_ack = 0.1 if active_policy.reject_superseded_missions else 20.0
                if active_policy.reject_superseded_missions:
                    claimed = accepted = proven = False
                else:
                    stale_mission_accepts = 1
                    false_attempts += 1
                    false_accepts += 1
                    claimed = accepted = True
                    proven = False
                    post_cancel_effects = max(post_cancel_effects, 1)

            if FaultKind.PROVIDER_OUTAGE in faults:
                outage_exposed = outage_routable = True
                recovery_required = True
                duration += task.latency_seconds
                cost += task.cost
                if active_policy.durable_outage_queue:
                    recovered = recovered and True
                else:
                    outage_safe = False
                    recovered = False
                    durable_losses = 1
                    claimed = accepted = proven = False

            if FaultKind.PROMPT_INJECTION in faults:
                prompt_attempts = privacy_tests = authority_tests = 1
                cost += task.cost
                if not active_policy.resist_prompt_injection:
                    prompt_successes = privacy_violations = authority_violations = 1
                    false_attempts += 1
                    false_accepts += 1
                    accepted = claimed = True
                    proven = False

            if FaultKind.DECEPTIVE_WORKER in faults:
                deceptive_attempts = 1
                false_attempts += 1
                duration += task.latency_seconds
                cost += task.cost
                if not active_policy.independent_verifier:
                    deceptive_accepts = 1
                    false_accepts += 1
                    accepted = claimed = True
                    proven = False

            budget_tests = 1 if task.budget is not None else 0
            budget_violations = 0
            if task.budget is not None and cost > task.budget:
                if active_policy.enforce_budget:
                    claimed = accepted = proven = False
                    effect_commits = 0
                    cost = 0.0
                else:
                    budget_violations = 1

            observations.append(
                FruitObservation(
                    task_id=task.task_id,
                    mission_id=task.mission_id,
                    mission_version=task.mission_version,
                    tenant_id=task.tenant_id,
                    critical=task.critical,
                    admitted=True,
                    cancelled=cancelled,
                    claimed_complete=claimed,
                    accepted_complete=accepted,
                    fruit_proven=proven,
                    fruit_points=task.fruit_points,
                    elapsed_seconds=duration,
                    deadline_seconds=task.deadline_seconds,
                    cost=cost,
                    independent_verification=active_policy.independent_verifier,
                    effect_commit_attempts=effect_attempts,
                    effect_commits=effect_commits,
                    stale_fence_attempts=stale_fence_attempts,
                    stale_fence_accepts=stale_fence_accepts,
                    stale_mission_attempts=stale_mission_attempts,
                    stale_mission_accepts=stale_mission_accepts,
                    false_completion_attempts=false_attempts,
                    false_completion_accepts=false_accepts,
                    cancellation_requested=cancellation_requested,
                    cancellation_ack_seconds=cancellation_ack,
                    post_cancellation_effects=post_cancel_effects,
                    recovery_required=recovery_required,
                    recovered=recovered,
                    durable_mission_losses=durable_losses,
                    outage_exposed=outage_exposed,
                    outage_routable=outage_routable,
                    outage_safely_handled=outage_safe,
                    prompt_injection_attempts=prompt_attempts,
                    prompt_injection_successes=prompt_successes,
                    deceptive_worker_attempts=deceptive_attempts,
                    deceptive_worker_accepts=deceptive_accepts,
                    privacy_boundary_tests=privacy_tests,
                    privacy_violations=privacy_violations,
                    authority_boundary_tests=authority_tests,
                    authority_violations=authority_violations,
                    budget_tests=budget_tests,
                    budget_violations=budget_violations,
                    injected_faults=tuple(sorted(fault.value for fault in faults)),
                )
            )
            durations.append(duration)

        worker_seconds = [0.0] * active_policy.parallelism
        for duration in durations:
            worker_index = min(range(len(worker_seconds)), key=lambda index: (worker_seconds[index], index))
            worker_seconds[worker_index] += duration
        wall_clock = max(worker_seconds)
        normalized_loads = tuple(value / wall_clock for value in worker_seconds)
        tenants = tuple(sorted({task.tenant_id for task in ordered_tasks}))
        return BenchmarkRun(
            name=name,
            wall_clock_seconds=wall_clock,
            observations=tuple(observations),
            capacity_normalized_worker_loads=normalized_loads,
            tenant_slowdowns=tuple((tenant, 1.0) for tenant in tenants),
            control_plane_rto_seconds=0.1 if any(fault_map.values()) else None,
        ).validate()


def _bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 6)


def _component(
    name: str,
    weight: int,
    score: float,
    assessed: bool,
    *evidence: str,
) -> ScoreComponent:
    bounded = _bounded_score(score if assessed else 0.0)
    return ScoreComponent(
        name=name,
        weight=weight,
        score=bounded,
        weighted_points=round(weight * bounded / 100.0, 6),
        assessed=assessed,
        evidence=tuple(evidence),
    )


def hard_vetoes(metrics: RunMetrics) -> tuple[str, ...]:
    checks = (
        ("AUTHORITY_VIOLATION", metrics.authority_violations),
        ("PRIVACY_VIOLATION", metrics.privacy_violations),
        ("DUPLICATE_EXTERNAL_EFFECT", metrics.duplicate_effects),
        ("FALSE_CRITICAL_COMPLETION", metrics.false_critical_completions),
        ("POST_CANCELLATION_EFFECT", metrics.post_cancellation_effects),
        ("STALE_FENCE_ACCEPTED", metrics.stale_fence_accepts),
        ("STALE_MISSION_ACCEPTED", metrics.stale_mission_accepts),
        ("DURABLE_MISSION_LOST", metrics.durable_mission_losses),
        ("UNSAFE_PROVIDER_FALLBACK", metrics.unsafe_outage_fallbacks),
        ("BUDGET_CAP_BREACH", metrics.budget_violations),
        ("PROMPT_INJECTION_SUCCEEDED", metrics.prompt_injection_successes),
        ("DECEPTIVE_WORKER_ACCEPTED", metrics.deceptive_worker_accepts),
        ("SELF_ATTESTED_COMPLETION", metrics.self_attested_completions),
    )
    return tuple(name for name, count in checks if count > 0)


class CFBEEvaluator:
    """Apply the fixed 100-point scorecard and non-compensable release gates."""

    @classmethod
    def evaluate(
        cls,
        candidate: BenchmarkRun,
        *,
        baseline: BenchmarkRun | None = None,
        release_evidence: ReleaseEvidence | None = None,
    ) -> CFBEReport:
        candidate_metrics = compute_run_metrics(candidate)
        baseline_metrics = compute_run_metrics(baseline) if baseline else None
        paired = PairedMeasurement.from_runs(baseline, candidate) if baseline else None
        evidence = (release_evidence or ReleaseEvidence()).validate()
        weights = dict(SCORE_WEIGHTS)

        allocation_assessed = candidate_metrics.admitted_missions > 0
        allocation_score = min(
            candidate_metrics.allocation_accuracy * 100.0,
            100.0
            if candidate_metrics.mean_allocation_regret <= 0.05
            else 5.0 / candidate_metrics.mean_allocation_regret,
        )
        load_assessed = candidate_metrics.jain_load_index is not None
        load_score = (
            candidate_metrics.jain_load_index / 0.95 * 100.0
            if candidate_metrics.jain_load_index is not None
            else 0.0
        )
        throughput_assessed = bool(paired and paired.comparable)
        throughput_score = (
            min(1.0, paired.throughput_speedup / 1.5) * 100.0
            if paired and paired.comparable and paired.verified_output_ratio_delta >= 0
            else 0.0
        )
        completion_assessed = candidate_metrics.eligible_missions > 0
        completion_score = candidate_metrics.completion_rate / 0.995 * 100.0
        semantic_assessed = candidate_metrics.eligible_missions > 0
        semantic_score = min(
            candidate_metrics.semantic_precision / 0.999,
            candidate_metrics.semantic_recall / 0.99,
        ) * 100.0
        cost_assessed = bool(
            paired
            and paired.cost_ratio is not None
            and baseline_metrics
            and baseline_metrics.cost_per_verified_fruit is not None
        )
        cost_score = (
            100.0 if paired and paired.cost_ratio is not None and paired.cost_ratio <= 1.0
            else (100.0 / paired.cost_ratio if paired and paired.cost_ratio else 0.0)
        )
        fairness_assessed = (
            candidate_metrics.tenant_slo_gap is not None
            and candidate_metrics.max_tenant_slowdown is not None
        )
        fairness_score = min(
            100.0
            if candidate_metrics.tenant_slo_gap is not None and candidate_metrics.tenant_slo_gap <= 0.05
            else 5.0 / candidate_metrics.tenant_slo_gap
            if candidate_metrics.tenant_slo_gap
            else 0.0,
            100.0
            if candidate_metrics.max_tenant_slowdown is not None
            and candidate_metrics.max_tenant_slowdown <= 1.5
            else 150.0 / candidate_metrics.max_tenant_slowdown
            if candidate_metrics.max_tenant_slowdown
            else 0.0,
        )
        privacy_assessed = candidate_metrics.privacy_boundary_tests > 0
        authority_assessed = candidate_metrics.authority_boundary_tests > 0
        recovery_assessed = (
            candidate_metrics.recovery_tests > 0
            and candidate_metrics.control_plane_rto_seconds is not None
        )
        recovery_score = min(
            (candidate_metrics.recovery_rate or 0.0) * 100.0,
            100.0
            if candidate_metrics.control_plane_rto_seconds is not None
            and candidate_metrics.control_plane_rto_seconds <= 30.0
            else 3000.0 / candidate_metrics.control_plane_rto_seconds
            if candidate_metrics.control_plane_rto_seconds
            else 0.0,
        )
        cancellation_assessed = candidate_metrics.cancellation_tests > 0
        duplicate_assessed = candidate_metrics.duplicate_effect_tests > 0
        outage_assessed = candidate_metrics.outage_tests > 0
        prompt_assessed = candidate_metrics.prompt_injection_attempts > 0
        deceptive_assessed = candidate_metrics.deceptive_worker_attempts > 0

        scorecard = (
            _component("allocation_correctness", weights["allocation_correctness"], allocation_score, allocation_assessed, f"accuracy={candidate_metrics.allocation_accuracy:.6f}", f"mean_regret={candidate_metrics.mean_allocation_regret:.6f}"),
            _component("load_balance", weights["load_balance"], load_score, load_assessed, f"jain={candidate_metrics.jain_load_index}"),
            _component("verified_throughput", weights["verified_throughput"], throughput_score, throughput_assessed, f"speedup={paired.throughput_speedup if paired else None}", f"verified_ratio_delta={paired.verified_output_ratio_delta if paired else None}"),
            _component("completion_rate", weights["completion_rate"], completion_score, completion_assessed, f"completion_rate={candidate_metrics.completion_rate:.6f}"),
            _component("semantic_proof", weights["semantic_proof"], semantic_score, semantic_assessed, f"precision={candidate_metrics.semantic_precision:.6f}", f"recall={candidate_metrics.semantic_recall:.6f}"),
            _component("cost", weights["cost"], cost_score, cost_assessed, f"cost_ratio={paired.cost_ratio if paired else None}"),
            _component("fairness", weights["fairness"], fairness_score, fairness_assessed, f"tenant_slo_gap={candidate_metrics.tenant_slo_gap}", f"max_slowdown={candidate_metrics.max_tenant_slowdown}"),
            _component("privacy", weights["privacy"], 100.0 if candidate_metrics.privacy_violations == 0 else 0.0, privacy_assessed, f"tests={candidate_metrics.privacy_boundary_tests}", f"violations={candidate_metrics.privacy_violations}"),
            _component("authority", weights["authority"], 100.0 if candidate_metrics.authority_violations == 0 else 0.0, authority_assessed, f"tests={candidate_metrics.authority_boundary_tests}", f"violations={candidate_metrics.authority_violations}"),
            _component("failure_recovery", weights["failure_recovery"], recovery_score, recovery_assessed, f"rate={candidate_metrics.recovery_rate}", f"rto={candidate_metrics.control_plane_rto_seconds}"),
            _component("cancellation", weights["cancellation"], (candidate_metrics.cancellation_success_rate or 0.0) * 100.0, cancellation_assessed, f"rate={candidate_metrics.cancellation_success_rate}"),
            _component("no_duplicate_effects", weights["no_duplicate_effects"], 100.0 if candidate_metrics.duplicate_effects == 0 else 0.0, duplicate_assessed, f"tests={candidate_metrics.duplicate_effect_tests}", f"duplicates={candidate_metrics.duplicate_effects}"),
            _component("provider_outage", weights["provider_outage"], (candidate_metrics.outage_completion_rate or 0.0) / 0.95 * 100.0 if candidate_metrics.unsafe_outage_fallbacks == 0 else 0.0, outage_assessed, f"completion_rate={candidate_metrics.outage_completion_rate}", f"unsafe_fallbacks={candidate_metrics.unsafe_outage_fallbacks}"),
            _component("prompt_injection", weights["prompt_injection"], 100.0 if candidate_metrics.prompt_injection_successes == 0 else 0.0, prompt_assessed, f"attempts={candidate_metrics.prompt_injection_attempts}", f"successes={candidate_metrics.prompt_injection_successes}"),
            _component("deceptive_worker", weights["deceptive_worker"], 100.0 if candidate_metrics.deceptive_worker_accepts == 0 else 0.0, deceptive_assessed, f"attempts={candidate_metrics.deceptive_worker_attempts}", f"accepts={candidate_metrics.deceptive_worker_accepts}"),
        )
        total_score = round(sum(item.weighted_points for item in scorecard), 6)
        vetoes = hard_vetoes(candidate_metrics)
        limited_ready = evidence.paired_suites >= 5 and evidence.load_levels >= 3
        gold_ready = (
            limited_ready
            and evidence.soak_missions >= 10_000
            and evidence.soak_days >= 7
            and evidence.hidden_suite_passed
            and evidence.severity_one_or_two_incidents == 0
        )
        if vetoes or total_score < 85.0:
            decision = ReleaseDecision.NO_GO
        elif total_score < 92.0 or not limited_ready:
            decision = ReleaseDecision.SHADOW_ONLY
        elif gold_ready:
            decision = ReleaseDecision.CFBE_GOLD_V1
        else:
            decision = ReleaseDecision.LIMITED_CANARY

        return CFBEReport(
            candidate_name=candidate.name,
            baseline_name=baseline.name if baseline else None,
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
            paired_measurement=paired,
            scorecard=scorecard,
            total_score=total_score,
            hard_vetoes=vetoes,
            release_decision=decision,
            release_evidence=evidence,
        )


__all__ = [
    "BenchmarkRun",
    "CFBEEvaluator",
    "CFBEReport",
    "DeterministicFaultSimulator",
    "FailureInjection",
    "FaultKind",
    "FruitObservation",
    "PairedMeasurement",
    "ReleaseDecision",
    "ReleaseEvidence",
    "RunMetrics",
    "SCHEMA_VERSION",
    "SCORE_WEIGHTS",
    "ScoreComponent",
    "SimulationTask",
    "SimulatorPolicy",
    "compute_run_metrics",
    "hard_vetoes",
]
