"""CFBE Ω Chat Hyperperformance Fabric v2.

Provider-neutral execution-control primitives harvested from current public
orchestration/reliability patterns. This module is effect-free: it decides,
scores and fences work but performs no provider action itself.

v2 focuses on the failure modes observed in long agentic chats:
- report/checkpoint loops that pre-empt actionable provider work,
- duplicate continuation directives,
- stale/unverified capability claims,
- repeated identical recovery routes,
- single-flight gaps and stale mutation workers,
- one global concurrency budget instead of per-surface bulkheads,
- tail latency without safe hedging/retry budgets,
- flat spans without trajectory-level no-progress detection,
- algorithm improvements that are not measured or promoted by evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
import re
from statistics import mean, quantiles
from typing import Sequence

SCHEMA = "CFBE-CHAT-HYPERPERFORMANCE-V2"
VERSION = "2.0.0"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _tokens(text: str) -> tuple[str, ...]:
    # Strip volatile ids/timestamps so semantically identical continuation
    # directives do not evade duplicate detection by changing receipts alone.
    text = re.sub(r"\b[0-9a-f]{16,64}\b", " <id> ", text.lower())
    text = re.sub(r"\b\d{4}-\d{2}-\d{2}(?:t[0-9:+.-]+)?\b", " <date> ", text)
    text = re.sub(r"\b\d{8,}\b", " <num> ", text)
    return tuple(re.findall(r"[a-z0-9_+-]+", text))


class ActionKind(str, Enum):
    PROVIDER_READ = "PROVIDER_READ"
    PROVIDER_WRITE = "PROVIDER_WRITE"
    LOCAL_ANALYSIS = "LOCAL_ANALYSIS"
    CHECKPOINT = "CHECKPOINT"
    REPORT = "REPORT"
    OWNER_GATE = "OWNER_GATE"


@dataclass(frozen=True, slots=True)
class ExecutionState:
    mission_id: str
    terminal_complete: bool = False
    actionable_provider_steps: tuple[str, ...] = ()
    owner_gate_required: bool = False
    owner_gate_request: str = ""
    new_evidence_refs: tuple[str, ...] = ()
    provider_progress_counter: int = 0
    local_checkpoint_count: int = 0


@dataclass(frozen=True, slots=True)
class ArbitrationDecision:
    allowed: bool
    required_action: str
    reasons: tuple[str, ...]


class ExecutionArbiter:
    """Enforces execute-before-report and suppresses local checkpoint loops."""

    def decide(self, state: ExecutionState, proposed: ActionKind) -> ArbitrationDecision:
        if not state.mission_id.strip():
            raise ValueError("MISSION_ID_REQUIRED")

        if state.terminal_complete:
            allowed = proposed is ActionKind.REPORT
            return ArbitrationDecision(
                allowed,
                "REPORT_FINAL",
                ("TERMINAL_STATE_ONLY_FINAL_REPORT",),
            )

        if state.owner_gate_required:
            if not state.owner_gate_request.strip():
                return ArbitrationDecision(False, "REPAIR_OWNER_GATE_REQUEST", ("OWNER_GATE_REQUEST_MUST_BE_PRECISE",))
            allowed = proposed is ActionKind.OWNER_GATE
            return ArbitrationDecision(
                allowed,
                "OWNER_GATE",
                ("OWNER_RESERVED_DECISION_REQUIRED",),
            )

        if state.actionable_provider_steps:
            required = state.actionable_provider_steps[0]
            if proposed in {ActionKind.REPORT, ActionKind.CHECKPOINT}:
                reasons = ["EXECUTABLE_PROVIDER_WORK_PRECEDES_REPORT"]
                if proposed is ActionKind.CHECKPOINT and state.local_checkpoint_count >= 1:
                    reasons.append("CHECKPOINT_LOOP_BLOCKED")
                return ArbitrationDecision(False, required, tuple(reasons))
            return ArbitrationDecision(True, required, ("ACTIONABLE_PROVIDER_PATH_PRESENT",))

        if proposed is ActionKind.CHECKPOINT and state.local_checkpoint_count >= 2:
            return ArbitrationDecision(False, "LOCAL_ANALYSIS_OR_RECOVERY", ("CHECKPOINT_AMPLIFICATION_BLOCKED",))

        return ArbitrationDecision(True, proposed.value, ("NO_HIGHER_PRIORITY_EXECUTABLE_STATE",))


@dataclass(frozen=True, slots=True)
class DirectiveComparison:
    duplicate: bool
    similarity: float
    allowed: bool
    reason: str


class DirectiveDuplicateGuard:
    """Blocks substantially identical continuation directives absent new execution evidence."""

    def __init__(self, threshold: float = 0.82) -> None:
        if not 0.5 <= threshold <= 1.0:
            raise ValueError("DIRECTIVE_SIMILARITY_THRESHOLD_INVALID")
        self.threshold = threshold

    @staticmethod
    def similarity(a: str, b: str) -> float:
        ta, tb = set(_tokens(a)), set(_tokens(b))
        if not ta and not tb:
            return 1.0
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    def compare(self, previous: str, proposed: str, *, new_execution_evidence: bool) -> DirectiveComparison:
        sim = self.similarity(previous, proposed)
        duplicate = sim >= self.threshold
        if duplicate and not new_execution_evidence:
            return DirectiveComparison(True, round(sim, 6), False, "DUPLICATE_DIRECTIVE_WITHOUT_NEW_EVIDENCE")
        return DirectiveComparison(duplicate, round(sim, 6), True, "NEW_EVIDENCE_OR_MATERIAL_DELTA")


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    surface: str
    action: str
    available: bool
    evidence_ref: str
    epoch: int
    observed_latency_ms: int = 0

    def validate(self) -> None:
        if not self.surface.strip() or not self.action.strip():
            raise ValueError("CAPABILITY_IDENTITY_REQUIRED")
        if not self.evidence_ref.strip():
            raise ValueError("CAPABILITY_EVIDENCE_REQUIRED")
        if self.epoch < 0 or self.observed_latency_ms < 0:
            raise ValueError("CAPABILITY_METRIC_INVALID")

    @property
    def key(self) -> tuple[str, str]:
        return (self.surface, self.action)


class CapabilitySnapshotCache:
    """Proof-bearing availability cache with shorter TTL for negative findings."""

    def __init__(self, *, positive_ttl_epochs: int = 3, negative_ttl_epochs: int = 1) -> None:
        if positive_ttl_epochs < 0 or negative_ttl_epochs < 0:
            raise ValueError("CAPABILITY_TTL_INVALID")
        self.positive_ttl_epochs = positive_ttl_epochs
        self.negative_ttl_epochs = negative_ttl_epochs
        self._records: dict[tuple[str, str], CapabilitySnapshot] = {}

    def put(self, snapshot: CapabilitySnapshot) -> None:
        snapshot.validate()
        current = self._records.get(snapshot.key)
        if current is None or snapshot.epoch >= current.epoch:
            self._records[snapshot.key] = snapshot

    def get(self, surface: str, action: str, *, current_epoch: int) -> CapabilitySnapshot | None:
        snap = self._records.get((surface, action))
        if snap is None:
            return None
        ttl = self.positive_ttl_epochs if snap.available else self.negative_ttl_epochs
        if current_epoch - snap.epoch > ttl:
            return None
        return snap

    def may_claim_unavailable(self, surface: str, action: str, *, current_epoch: int) -> bool:
        snap = self.get(surface, action, current_epoch=current_epoch)
        return snap is not None and not snap.available


@dataclass(frozen=True, slots=True)
class FailureObservation:
    failure_class: str
    surface: str
    operation: str
    route_id: str
    error_code: str
    evidence_ref: str

    @property
    def semantic_signature(self) -> str:
        return digest({
            "failure_class": self.failure_class.strip().upper(),
            "surface": self.surface.strip().lower(),
            "operation": self.operation.strip().upper(),
            "error_code": self.error_code.strip().upper(),
        })


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    action: str
    selected_route: str
    repeated_failures: int
    forbidden_routes: tuple[str, ...]
    architecture_remediation: bool
    reasons: tuple[str, ...]


class FailureEvolutionEngine:
    """Repeated semantic failure forces a materially different route."""

    def decide(
        self,
        current: FailureObservation,
        history: Sequence[FailureObservation],
        candidate_routes: Sequence[str],
    ) -> RecoveryDecision:
        if not current.evidence_ref.strip():
            raise ValueError("FAILURE_EVIDENCE_REQUIRED")
        same = [h for h in history if h.semantic_signature == current.semantic_signature]
        repeated = len(same) + 1
        attempted = tuple(dict.fromkeys([h.route_id for h in same] + [current.route_id]))
        alternatives = [r for r in candidate_routes if r and r not in attempted]

        if repeated >= 2:
            if alternatives:
                return RecoveryDecision(
                    "SWITCH_ROUTE",
                    alternatives[0],
                    repeated,
                    attempted,
                    repeated >= 3,
                    ("SAME_SEMANTIC_FAILURE_REPEATED", "MATERIALLY_DIFFERENT_ROUTE_REQUIRED"),
                )
            return RecoveryDecision(
                "ARCHITECTURE_REMEDIATION" if repeated >= 3 else "ALGORITHM_FOUNDRY",
                "",
                repeated,
                attempted,
                repeated >= 3,
                ("SAME_SEMANTIC_FAILURE_REPEATED", "NO_UNTRIED_ROUTE_AVAILABLE"),
            )

        return RecoveryDecision(
            "RETRY_OR_ALTERNATE",
            alternatives[0] if alternatives else current.route_id,
            repeated,
            (),
            False,
            ("FIRST_OBSERVATION",),
        )


@dataclass(frozen=True, slots=True)
class SingleFlightLease:
    semantic_key: str
    owner_id: str
    acquired_tick: int
    expires_tick: int
    generation: int


@dataclass(frozen=True, slots=True)
class LeaseDecision:
    state: str
    lease: SingleFlightLease


class SingleFlightLeaseBook:
    """Runtime duplicate suppression with expiry and leader/follower semantics."""

    def __init__(self) -> None:
        self._leases: dict[str, SingleFlightLease] = {}
        self._generation: dict[str, int] = {}

    def acquire(self, semantic_key: str, owner_id: str, *, now_tick: int, ttl_ticks: int) -> LeaseDecision:
        if not semantic_key.strip() or not owner_id.strip():
            raise ValueError("LEASE_IDENTITY_REQUIRED")
        if now_tick < 0 or ttl_ticks < 1:
            raise ValueError("LEASE_TIME_INVALID")
        existing = self._leases.get(semantic_key)
        if existing and now_tick < existing.expires_tick:
            return LeaseDecision("LEADER" if existing.owner_id == owner_id else "FOLLOWER", existing)

        generation = self._generation.get(semantic_key, 0) + 1
        self._generation[semantic_key] = generation
        lease = SingleFlightLease(semantic_key, owner_id, now_tick, now_tick + ttl_ticks, generation)
        self._leases[semantic_key] = lease
        return LeaseDecision("STALE_REPLACED" if existing else "LEADER", lease)

    def release(self, semantic_key: str, owner_id: str, generation: int) -> bool:
        lease = self._leases.get(semantic_key)
        if lease is None:
            return False
        if lease.owner_id != owner_id or lease.generation != generation:
            return False
        del self._leases[semantic_key]
        return True


@dataclass(frozen=True, slots=True)
class MutationFence:
    target_key: str
    owner_id: str
    token: int
    committed: bool = False


class MutationFenceBook:
    """Monotonic fencing token: stale workers cannot commit effects."""

    def __init__(self) -> None:
        self._current: dict[str, MutationFence] = {}
        self._counter: dict[str, int] = {}

    def acquire(self, target_key: str, owner_id: str) -> MutationFence:
        if not target_key.strip() or not owner_id.strip():
            raise ValueError("FENCE_IDENTITY_REQUIRED")
        token = self._counter.get(target_key, 0) + 1
        self._counter[target_key] = token
        fence = MutationFence(target_key, owner_id, token, False)
        self._current[target_key] = fence
        return fence

    def can_commit(self, fence: MutationFence) -> bool:
        return self._current.get(fence.target_key) == fence and not fence.committed

    def commit(self, fence: MutationFence) -> MutationFence:
        if not self.can_commit(fence):
            raise ValueError("STALE_MUTATION_FENCE")
        committed = MutationFence(fence.target_key, fence.owner_id, fence.token, True)
        self._current[fence.target_key] = committed
        return committed


@dataclass(frozen=True, slots=True)
class BulkheadProfile:
    surface: str
    max_concurrency: int
    max_retries_in_flight: int = 1
    rate_per_window: int = 100

    def validate(self) -> None:
        if not self.surface.strip():
            raise ValueError("BULKHEAD_SURFACE_REQUIRED")
        if min(self.max_concurrency, self.max_retries_in_flight, self.rate_per_window) < 0:
            raise ValueError("BULKHEAD_LIMIT_INVALID")
        if self.max_concurrency < 1 or self.rate_per_window < 1:
            raise ValueError("BULKHEAD_CAPACITY_INVALID")


@dataclass(frozen=True, slots=True)
class SchedulableUnit:
    unit_id: str
    surface: str
    estimated_ms: int
    priority: int = 50
    value_weight: float = 1.0
    deps: tuple[str, ...] = ()
    mutation_key: str = ""

    def validate(self) -> None:
        if not self.unit_id.strip() or not self.surface.strip():
            raise ValueError("SCHEDULABLE_IDENTITY_REQUIRED")
        if self.estimated_ms < 0 or self.value_weight < 0:
            raise ValueError("SCHEDULABLE_METRIC_INVALID")


@dataclass(frozen=True, slots=True)
class BulkheadWave:
    unit_ids: tuple[str, ...]
    surface_counts: tuple[tuple[str, int], ...]
    estimated_ms: int


class CriticalPathBulkheadPlanner:
    """Critical-path-first scheduling with per-surface bulkheads and one mutation per key."""

    @staticmethod
    def downstream_ms(units: Sequence[SchedulableUnit]) -> dict[str, int]:
        by_id = {u.unit_id: u for u in units}
        children: dict[str, list[str]] = {u.unit_id: [] for u in units}
        for u in units:
            u.validate()
            for dep in u.deps:
                if dep not in by_id:
                    raise ValueError("MISSING_DEPENDENCY:" + dep)
                children[dep].append(u.unit_id)
        memo: dict[str, int] = {}
        visiting: set[str] = set()

        def visit(uid: str) -> int:
            if uid in memo:
                return memo[uid]
            if uid in visiting:
                raise ValueError("DEPENDENCY_CYCLE_DETECTED")
            visiting.add(uid)
            child_cost = max((visit(c) for c in children[uid]), default=0)
            visiting.remove(uid)
            memo[uid] = by_id[uid].estimated_ms + child_cost
            return memo[uid]

        for uid in by_id:
            visit(uid)
        return memo

    def plan(
        self,
        units: Sequence[SchedulableUnit],
        profiles: Sequence[BulkheadProfile],
        *,
        global_max_parallel: int,
    ) -> tuple[BulkheadWave, ...]:
        if global_max_parallel < 1:
            raise ValueError("GLOBAL_PARALLEL_INVALID")
        by_id = {u.unit_id: u for u in units}
        if len(by_id) != len(units):
            raise ValueError("DUPLICATE_UNIT_ID")
        profile_map = {p.surface: p for p in profiles}
        for p in profiles:
            p.validate()
        missing_surfaces = sorted({u.surface for u in units} - set(profile_map))
        if missing_surfaces:
            raise ValueError("MISSING_BULKHEAD_PROFILE:" + ",".join(missing_surfaces))

        downstream = self.downstream_ms(units)
        completed: set[str] = set()
        remaining: set[str] = set(by_id)
        waves: list[BulkheadWave] = []

        while remaining:
            ready = [by_id[uid] for uid in remaining if set(by_id[uid].deps) <= completed]
            if not ready:
                raise ValueError("DEPENDENCY_CYCLE_DETECTED")

            ready.sort(
                key=lambda u: (
                    -(downstream[u.unit_id] * max(0.0001, u.value_weight)),
                    -u.priority,
                    u.estimated_ms,
                    u.unit_id,
                )
            )
            selected: list[SchedulableUnit] = []
            counts: dict[str, int] = {}
            mutation_keys: set[str] = set()
            for unit in ready:
                if len(selected) >= global_max_parallel:
                    break
                cap = profile_map[unit.surface].max_concurrency
                if counts.get(unit.surface, 0) >= cap:
                    continue
                if unit.mutation_key and unit.mutation_key in mutation_keys:
                    continue
                selected.append(unit)
                counts[unit.surface] = counts.get(unit.surface, 0) + 1
                if unit.mutation_key:
                    mutation_keys.add(unit.mutation_key)

            if not selected:
                raise ValueError("BULKHEAD_DEADLOCK")
            waves.append(BulkheadWave(
                tuple(u.unit_id for u in selected),
                tuple(sorted(counts.items())),
                max((u.estimated_ms for u in selected), default=0),
            ))
            for unit in selected:
                remaining.remove(unit.unit_id)
                completed.add(unit.unit_id)

        return tuple(waves)


@dataclass(frozen=True, slots=True)
class RetryBudget:
    max_tokens: float = 10.0
    token_ratio: float = 0.1
    tokens: float = 10.0

    def validate(self) -> None:
        if self.max_tokens <= 0 or self.token_ratio <= 0:
            raise ValueError("RETRY_BUDGET_INVALID")
        if not 0 <= self.tokens <= self.max_tokens:
            raise ValueError("RETRY_TOKENS_INVALID")

    def on_success(self) -> "RetryBudget":
        self.validate()
        return RetryBudget(self.max_tokens, self.token_ratio, min(self.max_tokens, self.tokens + self.token_ratio))

    def on_failure(self) -> "RetryBudget":
        self.validate()
        return RetryBudget(self.max_tokens, self.token_ratio, max(0.0, self.tokens - 1.0))

    @property
    def hedge_allowed(self) -> bool:
        self.validate()
        return self.tokens > self.max_tokens / 2.0


@dataclass(frozen=True, slots=True)
class HedgeRequest:
    read_only: bool
    idempotent: bool
    elapsed_ms: int
    route_p95_ms: int
    alternate_routes: tuple[str, ...]
    attempts_started: int = 1
    max_attempts: int = 2


@dataclass(frozen=True, slots=True)
class HedgeDecision:
    allowed: bool
    route_id: str
    reason: str


class TailHedgePolicy:
    """Safe tail-latency hedge: read-only + idempotent + retry budget + delayed."""

    def __init__(self, *, delay_fraction_of_p95: float = 0.9) -> None:
        if not 0.1 <= delay_fraction_of_p95 <= 2.0:
            raise ValueError("HEDGE_DELAY_INVALID")
        self.delay_fraction_of_p95 = delay_fraction_of_p95

    def decide(self, request: HedgeRequest, budget: RetryBudget) -> HedgeDecision:
        budget.validate()
        if not request.read_only or not request.idempotent:
            return HedgeDecision(False, "", "HEDGE_REQUIRES_READ_ONLY_IDEMPOTENT")
        if request.attempts_started >= request.max_attempts:
            return HedgeDecision(False, "", "HEDGE_MAX_ATTEMPTS_REACHED")
        if not request.alternate_routes:
            return HedgeDecision(False, "", "NO_ALTERNATE_ROUTE")
        if not budget.hedge_allowed:
            return HedgeDecision(False, "", "RETRY_BUDGET_THROTTLED")
        threshold = math.ceil(max(1, request.route_p95_ms) * self.delay_fraction_of_p95)
        if request.elapsed_ms < threshold:
            return HedgeDecision(False, "", "HEDGE_DELAY_NOT_REACHED")
        return HedgeDecision(True, request.alternate_routes[0], "TAIL_HEDGE_ALLOWED")


@dataclass(frozen=True, slots=True)
class TraceSpanV2:
    trace_id: str
    span_id: str
    parent_id: str
    kind: ActionKind
    latency_ms: int
    success: bool
    evidence_delta: int = 0
    provider_progress_delta: int = 0
    owner_interrupt: bool = False
    directive_duplicate: bool = False

    def validate(self) -> None:
        if not self.trace_id.strip() or not self.span_id.strip():
            raise ValueError("TRACE_IDENTITY_REQUIRED")
        if self.latency_ms < 0:
            raise ValueError("TRACE_LATENCY_INVALID")


@dataclass(frozen=True, slots=True)
class TrajectoryScore:
    span_count: int
    p95_ms: int
    provider_actions: int
    progress_events: int
    owner_interrupts: int
    duplicate_directives: int
    no_progress_cycles: int
    progress_ratio: float
    healthy: bool


class TrajectoryEvaluator:
    """Trajectory-level evaluation catches report/checkpoint loops, not just final text."""

    def __init__(self, *, no_progress_run: int = 2) -> None:
        if no_progress_run < 1:
            raise ValueError("NO_PROGRESS_RUN_INVALID")
        self.no_progress_run = no_progress_run

    def evaluate(self, spans: Sequence[TraceSpanV2]) -> TrajectoryScore:
        for span in spans:
            span.validate()
        if not spans:
            return TrajectoryScore(0, 0, 0, 0, 0, 0, 0, 0.0, True)

        latencies = sorted(s.latency_ms for s in spans)
        p95 = latencies[0] if len(latencies) == 1 else int(quantiles(latencies, n=20, method="inclusive")[18])
        provider_actions = sum(s.kind in {ActionKind.PROVIDER_READ, ActionKind.PROVIDER_WRITE} for s in spans)
        progress_events = sum((s.evidence_delta > 0 or s.provider_progress_delta > 0) for s in spans)
        owner_interrupts = sum(s.owner_interrupt for s in spans)
        duplicate_directives = sum(s.directive_duplicate for s in spans)

        run = 0
        no_progress_cycles = 0
        for span in spans:
            narrative_only = span.kind in {ActionKind.REPORT, ActionKind.CHECKPOINT}
            progressed = span.evidence_delta > 0 or span.provider_progress_delta > 0
            if narrative_only and not progressed:
                run += 1
                if run == self.no_progress_run:
                    no_progress_cycles += 1
            else:
                run = 0

        ratio = progress_events / len(spans)
        healthy = no_progress_cycles == 0 and duplicate_directives == 0
        return TrajectoryScore(
            len(spans),
            p95,
            provider_actions,
            progress_events,
            owner_interrupts,
            duplicate_directives,
            no_progress_cycles,
            round(ratio, 6),
            healthy,
        )


class OutputClass(str, Enum):
    INTERNAL_PROGRESS = "INTERNAL_PROGRESS"
    MILESTONE = "MILESTONE"
    OWNER_GATE = "OWNER_GATE"
    BLOCKER = "BLOCKER"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True, slots=True)
class OwnerAttentionBudget:
    max_internal_progress_messages: int = 0
    max_owner_gates: int = 1


class OwnerAttentionGovernor:
    """Suppresses routine internal chatter; milestones and true gates still pass."""

    def allow(
        self,
        output_class: OutputClass,
        *,
        internal_progress_emitted: int,
        owner_gates_emitted: int,
        budget: OwnerAttentionBudget,
    ) -> bool:
        if output_class in {OutputClass.MILESTONE, OutputClass.BLOCKER, OutputClass.TERMINAL}:
            return True
        if output_class is OutputClass.OWNER_GATE:
            return owner_gates_emitted < budget.max_owner_gates
        return internal_progress_emitted < budget.max_internal_progress_messages


class AlgorithmStage(str, Enum):
    A0_IDEA = "A0_IDEA"
    A1_SPECIFIED = "A1_SPECIFIED"
    A2_IMPLEMENTED = "A2_IMPLEMENTED"
    A3_TESTED = "A3_TESTED"
    A4_CURRENT_MISSION_SUCCESS = "A4_CURRENT_MISSION_SUCCESS"
    A5_REPEATED_REUSE = "A5_REPEATED_REUSE"
    A6_DEFAULT_CANDIDATE = "A6_DEFAULT_CANDIDATE"


@dataclass(frozen=True, slots=True)
class AlgorithmObservation:
    algorithm_id: str
    success: bool
    latency_ms: int
    proof_quality: float
    owner_interrupts: int
    regression: bool = False
    current_mission: bool = False


@dataclass(frozen=True, slots=True)
class AlgorithmSummary:
    algorithm_id: str
    runs: int
    success_rate: float
    avg_latency_ms: float
    avg_proof_quality: float
    owner_interrupts: int
    regressions: int
    stage: AlgorithmStage


class AlgorithmPerformanceLedger:
    """Evidence-based promotion; one successful workaround cannot become a universal default."""

    def summarize(
        self,
        algorithm_id: str,
        observations: Sequence[AlgorithmObservation],
        *,
        specified: bool = True,
        implemented: bool = True,
        deterministic_tests_passed: int = 0,
    ) -> AlgorithmSummary:
        obs = [o for o in observations if o.algorithm_id == algorithm_id]
        if not algorithm_id.strip():
            raise ValueError("ALGORITHM_ID_REQUIRED")
        for o in obs:
            if o.latency_ms < 0 or not 0 <= o.proof_quality <= 1 or o.owner_interrupts < 0:
                raise ValueError("ALGORITHM_OBSERVATION_INVALID")

        runs = len(obs)
        success_rate = (sum(o.success for o in obs) / runs) if runs else 0.0
        avg_latency = mean(o.latency_ms for o in obs) if runs else 0.0
        avg_proof = mean(o.proof_quality for o in obs) if runs else 0.0
        owner_interrupts = sum(o.owner_interrupts for o in obs)
        regressions = sum(o.regression for o in obs)
        current_success = any(o.success and o.current_mission for o in obs)
        successful_runs = sum(o.success for o in obs)

        stage = AlgorithmStage.A0_IDEA
        if specified:
            stage = AlgorithmStage.A1_SPECIFIED
        if implemented:
            stage = AlgorithmStage.A2_IMPLEMENTED
        if deterministic_tests_passed > 0:
            stage = AlgorithmStage.A3_TESTED
        if current_success:
            stage = AlgorithmStage.A4_CURRENT_MISSION_SUCCESS
        if successful_runs >= 3 and success_rate >= 0.90:
            stage = AlgorithmStage.A5_REPEATED_REUSE
        if successful_runs >= 5 and success_rate >= 0.95 and regressions == 0 and avg_proof >= 0.90:
            stage = AlgorithmStage.A6_DEFAULT_CANDIDATE

        return AlgorithmSummary(
            algorithm_id,
            runs,
            round(success_rate, 6),
            round(avg_latency, 3),
            round(avg_proof, 6),
            owner_interrupts,
            regressions,
            stage,
        )


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    provider_actions: int = 0
    evidence_refs: int = 0
    terminal_requirements_closed: int = 0
    new_algorithms_proven: int = 0
    owner_burden_reductions: int = 0


def monotonic_progress(previous: ProgressSnapshot, current: ProgressSnapshot) -> bool:
    """n-cycle progress court: at least one measurable axis must increase, none may go negative."""
    prev = (
        previous.provider_actions,
        previous.evidence_refs,
        previous.terminal_requirements_closed,
        previous.new_algorithms_proven,
        previous.owner_burden_reductions,
    )
    cur = (
        current.provider_actions,
        current.evidence_refs,
        current.terminal_requirements_closed,
        current.new_algorithms_proven,
        current.owner_burden_reductions,
    )
    if any(x < 0 for x in cur):
        raise ValueError("PROGRESS_METRIC_INVALID")
    return any(c > p for p, c in zip(prev, cur))


__all__ = [
    "ActionKind",
    "AlgorithmObservation",
    "AlgorithmPerformanceLedger",
    "AlgorithmStage",
    "AlgorithmSummary",
    "ArbitrationDecision",
    "BulkheadProfile",
    "BulkheadWave",
    "CapabilitySnapshot",
    "CapabilitySnapshotCache",
    "CriticalPathBulkheadPlanner",
    "DirectiveComparison",
    "DirectiveDuplicateGuard",
    "ExecutionArbiter",
    "ExecutionState",
    "FailureEvolutionEngine",
    "FailureObservation",
    "HedgeDecision",
    "HedgeRequest",
    "LeaseDecision",
    "MutationFence",
    "MutationFenceBook",
    "OwnerAttentionBudget",
    "OwnerAttentionGovernor",
    "OutputClass",
    "ProgressSnapshot",
    "RecoveryDecision",
    "RetryBudget",
    "SCHEMA",
    "SchedulableUnit",
    "SingleFlightLease",
    "SingleFlightLeaseBook",
    "TailHedgePolicy",
    "TraceSpanV2",
    "TrajectoryEvaluator",
    "TrajectoryScore",
    "VERSION",
    "digest",
    "monotonic_progress",
]
