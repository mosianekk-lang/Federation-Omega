"""Formation Ω Reconciliation Fabric v2.

Closed-loop, provider-neutral mission reconciliation built from existing Federation
primitives. The fabric treats a mission as desired state continuously reconciled
against observed state. It composes MCE durable history, Convergence Supervisor
freshness fences, AMCF proof-directed scheduling, failure horizons and independent
swarm roles. It also provides portable contracts for adaptive topology selection,
causal trace propagation, evaluator-driven challenger evolution, policy decisions,
and in-toto/SLSA-shaped attestations.

This module is A1_INTERNAL and creates no provider authority, background execution,
credential access, or external effect. Provider adapters must independently verify
fresh state and authority before honoring any effect-bearing request.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

from formation_omega.autonomic_fabric import (
    ActionCandidate,
    AuthorityCeiling,
    FailureForecast,
    FailureHorizon,
    MissionStateVector,
    MissionSwarmPlanner,
    MonotonicClosureGate,
    ProofDirectedScheduler,
    SwarmCell,
)
from formation_omega.convergence_supervisor import (
    ConvergenceSupervisor,
    ProviderSnapshot,
    SupervisorDecision,
)
from formation_omega.mission_convergence import ConvergenceLedger
from formation_omega.source_convergence import ChangeCapsule


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256(value: Any) -> str:
    payload = value if isinstance(value, str) else _canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


class ReconciliationAction(str, Enum):
    NOOP = "NOOP"
    OBSERVE = "OBSERVE"
    REFRESH_PROOF = "REFRESH_PROOF"
    RUN_CHECK = "RUN_CHECK"
    RECONCILE_SOURCE = "RECONCILE_SOURCE"
    REPLAY_COMMITTED_STEP = "REPLAY_COMMITTED_STEP"
    EXECUTE_INTERNAL_STEP = "EXECUTE_INTERNAL_STEP"
    REQUEST_PROVIDER_EFFECT = "REQUEST_PROVIDER_EFFECT"
    HOLD_POLICY = "HOLD_POLICY"
    HOLD_OWNER = "HOLD_OWNER"
    CLOSED = "CLOSED"


class TopologyMode(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    SINGLE_CONTROLLER = "SINGLE_CONTROLLER"
    PARALLEL_CELLS = "PARALLEL_CELLS"
    HYBRID = "HYBRID"
    BUILDER_FALSIFIER_WITNESS = "BUILDER_FALSIFIER_WITNESS"


class PolicyEffect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    HOLD = "HOLD"


@dataclass(frozen=True)
class DesiredMissionState:
    mission_id: str
    objective: str
    desired_state: str
    required_checks: tuple[str, ...] = ()
    required_proof_axes: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    rollback_required: bool = True
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    desired_sha256: str = ""

    @classmethod
    def create(
        cls,
        *,
        mission_id: str,
        objective: str,
        desired_state: str,
        required_checks: Iterable[str] = (),
        required_proof_axes: Iterable[str] = (),
        required_capabilities: Iterable[str] = (),
        rollback_required: bool = True,
        authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL,
    ) -> "DesiredMissionState":
        mission_id = str(mission_id).strip()
        objective = " ".join(str(objective).split())
        desired_state = str(desired_state).strip()
        if not mission_id or not objective or not desired_state:
            raise ValueError("mission_id, objective and desired_state are required")
        body = {
            "mission_id": mission_id,
            "objective": objective,
            "desired_state": desired_state,
            "required_checks": _clean(required_checks),
            "required_proof_axes": _clean(required_proof_axes),
            "required_capabilities": _clean(required_capabilities),
            "rollback_required": bool(rollback_required),
            "authority_ceiling": AuthorityCeiling(authority_ceiling).value,
        }
        return cls(
            mission_id=mission_id,
            objective=objective,
            desired_state=desired_state,
            required_checks=body["required_checks"],
            required_proof_axes=body["required_proof_axes"],
            required_capabilities=body["required_capabilities"],
            rollback_required=bool(rollback_required),
            authority_ceiling=AuthorityCeiling(authority_ceiling),
            desired_sha256=_sha256(body),
        )


@dataclass(frozen=True)
class ObservedMissionState:
    mission_id: str
    observed_state: str
    checks: Mapping[str, bool] = field(default_factory=dict)
    proof_axes: Mapping[str, bool] = field(default_factory=dict)
    capabilities: Mapping[str, bool] = field(default_factory=dict)
    rollback_available: bool = False
    provider_snapshot_sha256: str = ""
    causal_trace_id: str = ""
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "ObservedMissionState":
        if not self.mission_id.strip() or not self.observed_state.strip():
            raise ValueError("mission_id and observed_state are required")
        return self


@dataclass(frozen=True)
class StateGap:
    gap_id: str
    dimension: str
    expected: str
    observed: str
    action: ReconciliationAction
    priority: float
    reason: str


@dataclass(frozen=True)
class ReconciliationDelta:
    mission_id: str
    desired_sha256: str
    gaps: tuple[StateGap, ...]
    converged: bool
    delta_sha256: str


class StateReconciler:
    """Kubernetes-style desired-vs-observed reconciliation without provider effect."""

    @staticmethod
    def reconcile(desired: DesiredMissionState, observed: ObservedMissionState) -> ReconciliationDelta:
        observed.validate()
        if desired.mission_id != observed.mission_id:
            raise ValueError("desired and observed mission ids differ")
        gaps: list[StateGap] = []

        if observed.observed_state != desired.desired_state:
            gaps.append(
                StateGap(
                    gap_id="STATE-" + _sha256((desired.desired_state, observed.observed_state))[:16].upper(),
                    dimension="mission_state",
                    expected=desired.desired_state,
                    observed=observed.observed_state,
                    action=ReconciliationAction.RECONCILE_SOURCE,
                    priority=1.0,
                    reason="Desired terminal/current state differs from observed state.",
                )
            )

        for name in desired.required_checks:
            if not bool(observed.checks.get(name)):
                gaps.append(
                    StateGap(
                        gap_id="CHECK-" + _sha256(name)[:16].upper(),
                        dimension="check",
                        expected=f"{name}=PASS",
                        observed=f"{name}={observed.checks.get(name, 'MISSING')}",
                        action=ReconciliationAction.RUN_CHECK,
                        priority=0.95,
                        reason="Required exact-head check is not proven.",
                    )
                )

        for axis in desired.required_proof_axes:
            if not bool(observed.proof_axes.get(axis)):
                gaps.append(
                    StateGap(
                        gap_id="PROOF-" + _sha256(axis)[:16].upper(),
                        dimension="proof_axis",
                        expected=f"{axis}=PROVEN",
                        observed=f"{axis}={observed.proof_axes.get(axis, 'OPEN')}",
                        action=ReconciliationAction.REFRESH_PROOF,
                        priority=0.90,
                        reason="Required proof axis is not proven.",
                    )
                )

        for capability in desired.required_capabilities:
            if not bool(observed.capabilities.get(capability)):
                gaps.append(
                    StateGap(
                        gap_id="CAP-" + _sha256(capability)[:16].upper(),
                        dimension="capability",
                        expected=f"{capability}=AVAILABLE",
                        observed=f"{capability}={observed.capabilities.get(capability, 'UNVERIFIED')}",
                        action=ReconciliationAction.OBSERVE,
                        priority=0.75,
                        reason="Required capability is not freshly proven.",
                    )
                )

        if desired.rollback_required and not observed.rollback_available:
            gaps.append(
                StateGap(
                    gap_id="ROLLBACK-" + _sha256(desired.mission_id)[:16].upper(),
                    dimension="rollback",
                    expected="ROLLBACK_AVAILABLE",
                    observed="ROLLBACK_UNPROVEN",
                    action=ReconciliationAction.HOLD_POLICY,
                    priority=1.0,
                    reason="Rollback proof is mandatory before terminal promotion.",
                )
            )

        gaps.sort(key=lambda item: (-item.priority, item.gap_id))
        body = {
            "mission_id": desired.mission_id,
            "desired_sha256": desired.desired_sha256,
            "gaps": [asdict(item) for item in gaps],
        }
        return ReconciliationDelta(
            mission_id=desired.mission_id,
            desired_sha256=desired.desired_sha256,
            gaps=tuple(gaps),
            converged=not gaps,
            delta_sha256=_sha256(body),
        )


@dataclass(frozen=True)
class TaskGraphProfile:
    node_count: int
    edge_count: int
    ready_parallel_count: int
    shared_state_key_count: int
    deterministic_fraction: float
    uncertainty: float
    evidence_conflict: float
    consequential_fraction: float = 0.0

    def validate(self) -> "TaskGraphProfile":
        if self.node_count < 1 or self.edge_count < 0 or self.ready_parallel_count < 0 or self.shared_state_key_count < 0:
            raise ValueError("graph counts must be non-negative and node_count >= 1")
        for name in ("deterministic_fraction", "uncertainty", "evidence_conflict", "consequential_fraction"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        return self


@dataclass(frozen=True)
class TopologyDecision:
    mode: TopologyMode
    max_parallel: int
    require_falsifier: bool
    require_witness: bool
    reason_codes: tuple[str, ...]


class AdaptiveTopologyCompiler:
    """Selects deterministic/single/parallel/hybrid topology from task structure."""

    def compile(self, profile: TaskGraphProfile) -> TopologyDecision:
        profile.validate()
        parallel_ratio = min(1.0, profile.ready_parallel_count / max(1, profile.node_count))
        coupling = min(1.0, profile.shared_state_key_count / max(1, profile.ready_parallel_count or 1))
        reasons: list[str] = []

        if profile.deterministic_fraction >= 0.90 and profile.uncertainty <= 0.20 and profile.evidence_conflict <= 0.20:
            mode = TopologyMode.DETERMINISTIC
            max_parallel = max(1, min(4, profile.ready_parallel_count or 1))
            reasons.append("DETERMINISTIC_EXECUTOR_DOMINATES")
        elif profile.uncertainty >= 0.65 or profile.evidence_conflict >= 0.60:
            mode = TopologyMode.BUILDER_FALSIFIER_WITNESS
            max_parallel = 3
            reasons.append("HIGH_UNCERTAINTY_REQUIRES_INDEPENDENT_CHALLENGE")
        elif parallel_ratio >= 0.55 and coupling <= 0.35 and profile.consequential_fraction <= 0.25:
            mode = TopologyMode.PARALLEL_CELLS
            max_parallel = max(2, min(6, profile.ready_parallel_count))
            reasons.append("PARALLELISM_HIGH_COUPLING_LOW")
        elif parallel_ratio <= 0.25 or coupling >= 0.70:
            mode = TopologyMode.SINGLE_CONTROLLER
            max_parallel = 1
            reasons.append("SEQUENTIAL_OR_COUPLED_GRAPH")
        else:
            mode = TopologyMode.HYBRID
            max_parallel = max(2, min(4, profile.ready_parallel_count or 2))
            reasons.append("MIXED_DEPENDENCY_TOPOLOGY")

        require_falsifier = profile.uncertainty >= 0.40 or profile.evidence_conflict >= 0.35
        require_witness = profile.consequential_fraction > 0.0 or profile.evidence_conflict >= 0.50
        if require_falsifier:
            reasons.append("FALSIFIER_REQUIRED")
        if require_witness:
            reasons.append("WITNESS_REQUIRED")
        return TopologyDecision(mode, max_parallel, require_falsifier, require_witness, tuple(reasons))


@dataclass(frozen=True)
class OperationCandidate:
    action_id: str
    objective: str
    closure_leverage: float
    information_gain: float
    success_probability: float
    reversibility: float
    cost: float
    risk: float
    latency: float
    projected_state: MissionStateVector
    unlock_count: int = 0
    shared_state_key: str | None = None
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    external_effect: bool = False
    evidence_refs: tuple[str, ...] = ()

    def as_amcf(self) -> ActionCandidate:
        return ActionCandidate(
            action_id=self.action_id,
            objective=self.objective,
            closure_leverage=self.closure_leverage,
            information_gain=self.information_gain,
            success_probability=self.success_probability,
            reversibility=self.reversibility,
            cost=self.cost,
            risk=self.risk,
            latency=self.latency,
            unlock_count=self.unlock_count,
            shared_state_key=self.shared_state_key,
            authority_ceiling=self.authority_ceiling,
            external_effect=self.external_effect,
            evidence_refs=self.evidence_refs,
        )


@dataclass(frozen=True)
class ScheduledWave:
    topology: TopologyDecision
    selected_action_ids: tuple[str, ...]
    held_action_ids: tuple[str, ...]
    preempt_failure_fingerprints: tuple[str, ...]
    swarm: tuple[SwarmCell, ...]
    plan_sha256: str


class ProofDirectedWavePlanner:
    def __init__(self) -> None:
        self.scheduler = ProofDirectedScheduler(
            authority_ceiling=AuthorityCeiling.A1_INTERNAL,
            allow_external_effects=False,
        )
        self.closure_gate = MonotonicClosureGate()
        self.failure_horizon = FailureHorizon()
        self.swarm_planner = MissionSwarmPlanner()
        self.topology = AdaptiveTopologyCompiler()

    def plan(
        self,
        *,
        mission_id: str,
        objective: str,
        graph: TaskGraphProfile,
        before: MissionStateVector,
        operations: Sequence[OperationCandidate],
        forecasts: Sequence[FailureForecast] = (),
        required_capabilities: Iterable[str] = (),
    ) -> ScheduledWave:
        topology = self.topology.compile(graph)
        accepted: list[OperationCandidate] = []
        held: list[str] = []
        for operation in operations:
            gate = self.closure_gate.evaluate(before, operation.projected_state)
            if not gate.accepted:
                held.append(operation.action_id)
                continue
            accepted.append(operation)
        scheduled = self.scheduler.ready_wave(
            (item.as_amcf() for item in accepted),
            max_parallel=topology.max_parallel,
        )
        selected = tuple(item.action.action_id for item in scheduled)
        held.extend(item.action_id for item in accepted if item.action_id not in set(selected))
        preemptions = self.failure_horizon.preempt(forecasts)
        swarm: tuple[SwarmCell, ...] = ()
        if topology.mode in {TopologyMode.BUILDER_FALSIFIER_WITNESS, TopologyMode.HYBRID, TopologyMode.PARALLEL_CELLS}:
            all_cells = self.swarm_planner.plan(
                mission_id=mission_id,
                objective=objective,
                required_capabilities=required_capabilities,
            )
            if topology.mode == TopologyMode.BUILDER_FALSIFIER_WITNESS:
                swarm = tuple(cell for cell in all_cells if cell.role.value in {"BUILDER", "FALSIFIER", "WITNESS"})
            else:
                swarm = all_cells
        body = {
            "mission_id": mission_id,
            "topology": asdict(topology),
            "selected": selected,
            "held": sorted(set(held)),
            "preemptions": [item.fingerprint for item in preemptions],
            "swarm": [cell.cell_id for cell in swarm],
        }
        return ScheduledWave(
            topology=topology,
            selected_action_ids=selected,
            held_action_ids=tuple(sorted(set(held))),
            preempt_failure_fingerprints=tuple(item.fingerprint for item in preemptions),
            swarm=swarm,
            plan_sha256=_sha256(body),
        )


@dataclass(frozen=True)
class ReplayStepReceipt:
    mission_id: str
    step_key: str
    input_sha256: str
    result_ref: str
    result_sha256: str
    event_hash: str
    replayed: bool


class DurableReplayKernel:
    """Temporal/LangGraph-style replay semantics on the existing MCE ledger.

    The kernel records only public-safe hashes/references. It never executes provider
    effects itself. A committed step key cannot be reused with different input.
    """

    EVENT = "REPLAY_STEP_COMMITTED_V2"

    def __init__(self, ledger: ConvergenceLedger) -> None:
        self.ledger = ledger

    def _existing(self, mission_id: str, step_key: str) -> ReplayStepReceipt | None:
        for event in self.ledger.events(mission_id):
            if event.event_type != self.EVENT or event.payload.get("step_key") != step_key:
                continue
            return ReplayStepReceipt(
                mission_id=mission_id,
                step_key=step_key,
                input_sha256=str(event.payload["input_sha256"]),
                result_ref=str(event.payload["result_ref"]),
                result_sha256=str(event.payload["result_sha256"]),
                event_hash=event.event_hash,
                replayed=True,
            )
        return None

    def commit(
        self,
        *,
        mission_id: str,
        step_key: str,
        input_payload: Mapping[str, Any],
        result_ref: str,
        result_digest_source: Any,
    ) -> ReplayStepReceipt:
        step_key = str(step_key).strip()
        result_ref = str(result_ref).strip()
        if not step_key or not result_ref:
            raise ValueError("step_key and result_ref are required")
        input_sha = _sha256(dict(input_payload))
        result_sha = _sha256(result_digest_source)
        existing = self._existing(mission_id, step_key)
        if existing is not None:
            if existing.input_sha256 != input_sha:
                raise RuntimeError("REPLAY_STEP_INPUT_CONFLICT")
            if existing.result_sha256 != result_sha or existing.result_ref != result_ref:
                raise RuntimeError("REPLAY_STEP_RESULT_CONFLICT")
            return existing
        payload = {
            "step_key": step_key,
            "input_sha256": input_sha,
            "result_ref": result_ref,
            "result_sha256": result_sha,
        }
        event = self.ledger.append(
            mission_id=mission_id,
            event_type=self.EVENT,
            payload=payload,
            idempotency_key=f"replay:{mission_id}:{step_key}:{input_sha}",
        )
        return ReplayStepReceipt(mission_id, step_key, input_sha, result_ref, result_sha, event.event_hash, False)

    def resume(self, *, mission_id: str, step_key: str, input_payload: Mapping[str, Any]) -> ReplayStepReceipt | None:
        existing = self._existing(mission_id, step_key)
        if existing is None:
            return None
        if existing.input_sha256 != _sha256(dict(input_payload)):
            raise RuntimeError("REPLAY_STEP_INPUT_CONFLICT")
        return existing


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    trace_flags: str = "01"

    @classmethod
    def create(cls, seed: str) -> "TraceContext":
        digest = _sha256(seed)
        trace_id = digest[:32]
        span_id = digest[32:48]
        if set(trace_id) == {"0"} or set(span_id) == {"0"}:
            raise ValueError("trace ids may not be all zero")
        return cls(trace_id, span_id)

    @classmethod
    def parse(cls, traceparent: str) -> "TraceContext":
        match = re.fullmatch(r"00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})", traceparent.strip())
        if not match or set(match.group(1)) == {"0"} or set(match.group(2)) == {"0"}:
            raise ValueError("invalid W3C traceparent")
        return cls(match.group(1), match.group(2), match.group(3))

    @property
    def traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"

    def child(self, operation: str) -> "TraceContext":
        child_span = _sha256(f"{self.trace_id}:{self.span_id}:{operation}")[:16]
        return TraceContext(self.trace_id, child_span, self.trace_flags)


@dataclass(frozen=True)
class PolicyInput:
    action: str
    authority_ceiling: AuthorityCeiling
    external_effect: bool
    semantic_conflict: bool
    required_checks_passed: bool
    rollback_available: bool
    exact_snapshot_bound: bool
    owner_authorized: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    effect: PolicyEffect
    reason_codes: tuple[str, ...]


class PolicyKernel:
    """OPA-shaped default-deny policy semantics implemented portably in stdlib."""

    @staticmethod
    def evaluate(value: PolicyInput) -> PolicyDecision:
        reasons: list[str] = []
        if value.semantic_conflict:
            return PolicyDecision(PolicyEffect.DENY, ("SEMANTIC_CONFLICT",))
        if not value.exact_snapshot_bound:
            return PolicyDecision(PolicyEffect.DENY, ("EXACT_PROVIDER_SNAPSHOT_REQUIRED",))
        if not value.required_checks_passed:
            reasons.append("REQUIRED_CHECKS_INCOMPLETE")
        if not value.rollback_available:
            reasons.append("ROLLBACK_UNPROVEN")
        if value.external_effect:
            if value.authority_ceiling == AuthorityCeiling.A1_INTERNAL:
                return PolicyDecision(PolicyEffect.DENY, ("A1_INTERNAL_NO_EXTERNAL_EFFECT",))
            if not value.owner_authorized:
                return PolicyDecision(PolicyEffect.HOLD, ("OWNER_AUTHORIZATION_REQUIRED",))
        if reasons:
            return PolicyDecision(PolicyEffect.HOLD, tuple(reasons))
        return PolicyDecision(PolicyEffect.ALLOW, ("POLICY_SATISFIED",))


@dataclass(frozen=True)
class EvaluationProfile:
    profile_id: str
    weights: Mapping[str, float]
    minimums: Mapping[str, float] = field(default_factory=dict)
    fatal_dimensions: tuple[str, ...] = ()

    def validate(self) -> "EvaluationProfile":
        if not self.profile_id.strip() or not self.weights:
            raise ValueError("profile_id and weights are required")
        if any(float(weight) <= 0 for weight in self.weights.values()):
            raise ValueError("weights must be positive")
        for mapping in (self.minimums,):
            if any(not 0.0 <= float(value) <= 1.0 for value in mapping.values()):
                raise ValueError("minimums must be in [0,1]")
        return self


@dataclass(frozen=True)
class EvolutionCandidate:
    candidate_id: str
    parent_ids: tuple[str, ...]
    metrics: Mapping[str, float]
    artifact_ref: str
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "EvolutionCandidate":
        if not self.candidate_id.strip() or not self.artifact_ref.strip():
            raise ValueError("candidate_id and artifact_ref are required")
        if any(not 0.0 <= float(value) <= 1.0 for value in self.metrics.values()):
            raise ValueError("candidate metrics must be in [0,1]")
        return self


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    score: float
    fatal_regressions: tuple[str, ...]
    missing_dimensions: tuple[str, ...]
    promotion_eligible: bool


@dataclass(frozen=True)
class EvolutionTournamentResult:
    incumbent_id: str
    evaluations: tuple[CandidateEvaluation, ...]
    pareto_frontier_ids: tuple[str, ...]
    champion_id: str
    promoted: bool
    result_sha256: str


class EvolutionaryChallengerLab:
    """AlphaEvolve-inspired evaluator loop; candidate generation stays pluggable."""

    @staticmethod
    def evaluate(candidate: EvolutionCandidate, profile: EvaluationProfile) -> CandidateEvaluation:
        candidate.validate()
        profile.validate()
        missing = tuple(sorted(set(profile.weights) - set(candidate.metrics)))
        fatal: list[str] = []
        for dimension, minimum in profile.minimums.items():
            if float(candidate.metrics.get(dimension, 0.0)) < float(minimum):
                fatal.append(dimension)
        total_weight = sum(float(weight) for weight in profile.weights.values())
        score = 0.0
        if not missing:
            score = sum(
                float(profile.weights[name]) * float(candidate.metrics[name])
                for name in profile.weights
            ) / total_weight
        fatal.extend(name for name in profile.fatal_dimensions if float(candidate.metrics.get(name, 0.0)) <= 0.0)
        fatal_tuple = tuple(sorted(set(fatal)))
        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            score=round(score, 9),
            fatal_regressions=fatal_tuple,
            missing_dimensions=missing,
            promotion_eligible=not fatal_tuple and not missing,
        )

    @staticmethod
    def pareto_frontier(candidates: Sequence[EvolutionCandidate], dimensions: Sequence[str]) -> tuple[str, ...]:
        frontier: list[str] = []
        for candidate in candidates:
            candidate.validate()
            dominated = False
            for other in candidates:
                if other.candidate_id == candidate.candidate_id:
                    continue
                ge_all = all(float(other.metrics.get(dim, 0.0)) >= float(candidate.metrics.get(dim, 0.0)) for dim in dimensions)
                gt_any = any(float(other.metrics.get(dim, 0.0)) > float(candidate.metrics.get(dim, 0.0)) for dim in dimensions)
                if ge_all and gt_any:
                    dominated = True
                    break
            if not dominated:
                frontier.append(candidate.candidate_id)
        return tuple(sorted(frontier))

    def tournament(
        self,
        *,
        incumbent: EvolutionCandidate,
        challengers: Sequence[EvolutionCandidate],
        profile: EvaluationProfile,
        minimum_improvement: float = 0.01,
    ) -> EvolutionTournamentResult:
        pool = (incumbent, *tuple(challengers))
        evaluations = tuple(self.evaluate(candidate, profile) for candidate in pool)
        by_id = {item.candidate_id: item for item in evaluations}
        incumbent_eval = by_id[incumbent.candidate_id]
        eligible = [item for item in evaluations if item.promotion_eligible]
        champion = max(eligible, key=lambda item: (item.score, item.candidate_id)) if eligible else incumbent_eval
        promoted = (
            champion.candidate_id != incumbent.candidate_id
            and champion.score >= incumbent_eval.score + float(minimum_improvement)
            and champion.promotion_eligible
        )
        frontier = self.pareto_frontier(pool, tuple(profile.weights))
        body = {
            "incumbent": incumbent.candidate_id,
            "evaluations": [asdict(item) for item in evaluations],
            "frontier": frontier,
            "champion": champion.candidate_id,
            "promoted": promoted,
        }
        return EvolutionTournamentResult(
            incumbent_id=incumbent.candidate_id,
            evaluations=evaluations,
            pareto_frontier_ids=frontier,
            champion_id=champion.candidate_id,
            promoted=promoted,
            result_sha256=_sha256(body),
        )


@dataclass(frozen=True)
class AttestationEnvelope:
    statement: Mapping[str, Any]
    statement_sha256: str
    signing_required: bool = True

    @classmethod
    def create(
        cls,
        *,
        subjects: Mapping[str, str],
        predicate_type: str,
        predicate: Mapping[str, Any],
        builder_id: str,
    ) -> "AttestationEnvelope":
        normalized_subjects = [
            {"name": name, "digest": {"sha256": digest}}
            for name, digest in sorted(subjects.items())
        ]
        if not normalized_subjects or any(not item["digest"]["sha256"] for item in normalized_subjects):
            raise ValueError("attestation subjects require sha256 digests")
        statement = {
            "_type": "https://in-toto.io/Statement/v1",
            "subject": normalized_subjects,
            "predicateType": str(predicate_type),
            "predicate": {"builder": {"id": str(builder_id)}, **dict(predicate)},
        }
        return cls(statement=statement, statement_sha256=_sha256(statement), signing_required=True)


@dataclass(frozen=True)
class FabricPlan:
    mission_id: str
    delta: ReconciliationDelta
    topology: TopologyDecision
    wave: ScheduledWave | None
    source_decision: SupervisorDecision | None
    policy: PolicyDecision
    trace: TraceContext
    plan_sha256: str


class ReconciliationFabricV2:
    """Closed-loop controller facade. Plans only; adapters execute effects separately."""

    def __init__(self, supervisor: ConvergenceSupervisor | None = None) -> None:
        self.supervisor = supervisor or ConvergenceSupervisor()
        self.state = StateReconciler()
        self.topology = AdaptiveTopologyCompiler()
        self.wave_planner = ProofDirectedWavePlanner()

    def plan(
        self,
        *,
        desired: DesiredMissionState,
        observed: ObservedMissionState,
        graph: TaskGraphProfile,
        before: MissionStateVector,
        operations: Sequence[OperationCandidate] = (),
        forecasts: Sequence[FailureForecast] = (),
        capsule: ChangeCapsule | None = None,
        provider_snapshot: ProviderSnapshot | None = None,
        semantic_compatibility: Mapping[str, bool] | None = None,
    ) -> FabricPlan:
        delta = self.state.reconcile(desired, observed)
        topology = self.topology.compile(graph)
        source_decision: SupervisorDecision | None = None
        if capsule is not None:
            if provider_snapshot is None:
                raise ValueError("source reconciliation requires provider_snapshot")
            source_decision = self.supervisor.compile(
                capsule,
                provider_snapshot,
                semantic_compatibility=semantic_compatibility,
            )
        wave: ScheduledWave | None = None
        if operations:
            wave = self.wave_planner.plan(
                mission_id=desired.mission_id,
                objective=desired.objective,
                graph=graph,
                before=before,
                operations=operations,
                forecasts=forecasts,
                required_capabilities=desired.required_capabilities,
            )
        semantic_conflict = bool(
            source_decision and source_decision.action.value == "RECONCILE_SEMANTIC_CONFLICT"
        )
        exact_snapshot_bound = bool(provider_snapshot) if capsule is not None else True
        policy = PolicyKernel.evaluate(
            PolicyInput(
                action="RECONCILE",
                authority_ceiling=desired.authority_ceiling,
                external_effect=False,
                semantic_conflict=semantic_conflict,
                required_checks_passed=all(bool(observed.checks.get(name)) for name in desired.required_checks),
                rollback_available=observed.rollback_available or not desired.rollback_required,
                exact_snapshot_bound=exact_snapshot_bound,
            )
        )
        trace = TraceContext.create(
            f"{desired.mission_id}:{desired.desired_sha256}:{delta.delta_sha256}:{observed.provider_snapshot_sha256}"
        )
        body = {
            "mission_id": desired.mission_id,
            "delta": delta.delta_sha256,
            "topology": asdict(topology),
            "wave": wave.plan_sha256 if wave else None,
            "source_action": source_decision.action.value if source_decision else None,
            "policy": asdict(policy),
            "traceparent": trace.traceparent,
        }
        return FabricPlan(
            mission_id=desired.mission_id,
            delta=delta,
            topology=topology,
            wave=wave,
            source_decision=source_decision,
            policy=policy,
            trace=trace,
            plan_sha256=_sha256(body),
        )


__all__ = [
    "AdaptiveTopologyCompiler",
    "AttestationEnvelope",
    "CandidateEvaluation",
    "DesiredMissionState",
    "DurableReplayKernel",
    "EvaluationProfile",
    "EvolutionCandidate",
    "EvolutionTournamentResult",
    "EvolutionaryChallengerLab",
    "FabricPlan",
    "ObservedMissionState",
    "OperationCandidate",
    "PolicyDecision",
    "PolicyEffect",
    "PolicyInput",
    "PolicyKernel",
    "ProofDirectedWavePlanner",
    "ReconciliationAction",
    "ReconciliationDelta",
    "ReconciliationFabricV2",
    "ReplayStepReceipt",
    "ScheduledWave",
    "StateGap",
    "StateReconciler",
    "TaskGraphProfile",
    "TopologyDecision",
    "TopologyMode",
    "TraceContext",
]
