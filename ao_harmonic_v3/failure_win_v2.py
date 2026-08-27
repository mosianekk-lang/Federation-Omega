from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable

from .evolution import fitness
from .horizon import HorizonOmega
from .models import FederationEvent, PerformanceVector
from .science_and_routes import FormationEngine, Route


class FailureEventType(str, Enum):
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    REGRESSION = "REGRESSION"
    CLAIM_FRUIT_CONTRADICTION = "CLAIM_FRUIT_CONTRADICTION"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    OWNER_CORRECTION = "OWNER_CORRECTION"
    SLO_BREACH = "SLO_BREACH"
    CANARY_FAILURE = "CANARY_FAILURE"
    PRECURSOR_RISK = "PRECURSOR_RISK"


class FailureWinState(str, Enum):
    OBSERVE = "OBSERVE"
    PREEMPTION_READY = "PREEMPTION_READY"
    REPAIR_CYCLE_OPEN = "REPAIR_CYCLE_OPEN"
    ROUTE_SELECTED = "ROUTE_SELECTED"
    QUARANTINED = "QUARANTINED"
    BOUNDED_WIN = "BOUNDED_WIN"
    OPERATIONAL_WIN_VERIFIED = "OPERATIONAL_WIN_VERIFIED"


class RecoveryAction(str, Enum):
    OBSERVE = "OBSERVE"
    PREEMPT = "PREEMPT"
    PATCH_EXISTING = "PATCH_EXISTING"
    CREATE_CANDIDATE = "CREATE_CANDIDATE"
    RACE_CANDIDATES = "RACE_CANDIDATES"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class StageBudget:
    stage: str
    budget_seconds: float
    observed_seconds: float | None = None
    hard_commitment: bool = False

    @property
    def breached(self) -> bool:
        return self.observed_seconds is not None and self.observed_seconds > self.budget_seconds


@dataclass(frozen=True)
class CausalHypothesis:
    hypothesis_id: str
    statement: str
    confidence: float
    supporting_evidence: tuple[str, ...] = ()
    conflicting_evidence: tuple[str, ...] = ()
    falsification_test: str = ""
    predicted_if_true: str = ""
    expected_information_gain: float = 0.5
    test_cost: float = 1.0

    @property
    def falsifiable(self) -> bool:
        return bool(self.falsification_test.strip() and self.predicted_if_true.strip())


@dataclass(frozen=True)
class RecoveryRoute:
    route_id: str
    route_type: str
    performance: PerformanceVector
    available: bool = True
    authorised: bool = True
    zero_or_included_cost: bool = True
    rollback_available: bool = True
    materially_different: bool = True
    provider_neutral: bool = True
    proof_strength: float = 0.0
    reversibility: float = 0.0
    strategic_value: float = 0.0
    expected_value: float = 0.0
    expected_cost: float = 0.0
    expected_risk: float = 0.0


@dataclass(frozen=True)
class ReceiverAttestation:
    receiver_id: str
    kernel_invoked: bool
    behavior_proven: bool
    current: bool
    independent_readback: bool
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class WinEvidence:
    failure_fact_preserved: bool = False
    causal_model_recorded: bool = False
    falsification_executed: bool = False
    authority_current: bool = False
    cost_allowed: bool = False
    failure_first_test_passed: bool = False
    healthy_path_test_passed: bool = False
    rollback_test_passed: bool = False
    forward_canary_passed: bool = False
    independent_semantic_readback: bool = False
    positive_value: bool = False
    no_regression: bool = False
    owner_burden_not_increased: bool = False
    provider_receipt_present: bool = False
    repeated_successes: int = 0
    soak_seconds: float = 0.0
    proof_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class FailureObservation:
    event_id: str
    event_type: FailureEventType
    system_id: str
    objective: str
    claim: str
    observed_fruit: str
    desired_outcome: str
    failure_code: str
    provider: str = ""
    configuration_hash: str = ""
    dependency_refs: tuple[str, ...] = ()
    failed_route_id: str = ""
    material: bool = True
    recurrence_count: int = 1
    owner_burden_delta: float = 0.0
    precursor_signals: tuple[str, ...] = ()
    recent_route_history: tuple[str, ...] = ()
    stage_budgets: tuple[StageBudget, ...] = ()


@dataclass(frozen=True)
class FailureWinRequest:
    observation: FailureObservation
    incumbent: PerformanceVector = field(default_factory=PerformanceVector)
    hypotheses: tuple[CausalHypothesis, ...] = ()
    routes: tuple[RecoveryRoute, ...] = ()
    evidence: WinEvidence = field(default_factory=WinEvidence)
    receiver_attestations: tuple[ReceiverAttestation, ...] = ()
    receiver_manifest_complete: bool = False
    estate_scope_claim: bool = False
    provider_dependent: bool = False
    required_soak_seconds: float = 300.0
    required_repeated_successes: int = 3
    maximum_race_width: int = 3


@dataclass(frozen=True)
class FailureGenomeRecord:
    fingerprint: str
    failure_code: str
    system_id: str
    first_event_id: str
    recurrence: int
    last_state: str
    quarantined_routes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProofGraphAssessment:
    required_nodes: tuple[str, ...]
    satisfied_nodes: tuple[str, ...]
    missing_nodes: tuple[str, ...]
    complete: bool


@dataclass(frozen=True)
class FailureWinResult:
    kernel: str
    version: str
    state: FailureWinState
    action: RecoveryAction
    fingerprint: str
    portable_fingerprint: str
    recurrence: int
    selected_route_ids: tuple[str, ...]
    ranked_hypothesis_ids: tuple[str, ...]
    next_falsification_test: str
    vector_gate_passed: bool
    measured_fitness_ratio: float | None
    protected_regressions: tuple[str, ...]
    time_budget_breaches: tuple[str, ...]
    oscillation_detected: bool
    receiver_manifest_hash: str
    proof_graph: ProofGraphAssessment
    prewarm_route_ids: tuple[str, ...]
    horizon_depth: int
    kpis: dict[str, Any]
    next_actions: tuple[str, ...]
    truth_boundary: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        value["action"] = self.action.value
        return value


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FailureToOperationalWinKernelV2:
    """Closed-loop failure -> recovery -> proof -> prevention control.

    The kernel is deterministic decision support. It does not perform provider
    mutations, grant authority, or self-promote receiver maturity.
    """

    KERNEL_ID = "FAILURE-TO-OPERATIONAL-WIN-V2"
    VERSION = "2.0.0"

    POSITIVE_DIMENSIONS = (
        "quality",
        "reliability",
        "proof",
        "speed",
        "owner_time_recovered",
        "privacy_gain",
        "recovery_gain",
        "simplicity_gain",
    )
    PROTECTED_POSITIVE = ("quality", "reliability", "proof")
    PROTECTED_COSTS = (
        "false_blocks",
        "error_cost",
        "owner_burden",
        "privacy_risk",
        "regression_risk",
    )

    def __init__(self, *, horizon: HorizonOmega | None = None, formation: FormationEngine | None = None) -> None:
        self.horizon = horizon or HorizonOmega()
        self.formation = formation or FormationEngine()
        self._genome: dict[str, FailureGenomeRecord] = {}

    @staticmethod
    def fingerprint(observation: FailureObservation) -> str:
        identity = {
            "system_id": observation.system_id,
            "provider": observation.provider,
            "failure_code": observation.failure_code,
            "claim": " ".join(observation.claim.split()).lower(),
            "observed_fruit": " ".join(observation.observed_fruit.split()).lower(),
            "desired_outcome": " ".join(observation.desired_outcome.split()).lower(),
            "configuration_hash": observation.configuration_hash,
            "dependency_refs": sorted(observation.dependency_refs),
        }
        return "fwg-" + _canonical_hash(identity)[:24]

    @staticmethod
    def portable_fingerprint(observation: FailureObservation) -> str:
        identity = {
            "failure_code": observation.failure_code,
            "claim": " ".join(observation.claim.split()).lower(),
            "observed_fruit": " ".join(observation.observed_fruit.split()).lower(),
            "desired_outcome": " ".join(observation.desired_outcome.split()).lower(),
        }
        return "fwp-" + _canonical_hash(identity)[:24]

    @staticmethod
    def receiver_manifest_hash(attestations: Iterable[ReceiverAttestation]) -> str:
        payload = [
            {
                "receiver_id": item.receiver_id,
                "kernel_invoked": item.kernel_invoked,
                "behavior_proven": item.behavior_proven,
                "current": item.current,
                "independent_readback": item.independent_readback,
                "evidence_refs": sorted(item.evidence_refs),
            }
            for item in sorted(attestations, key=lambda value: value.receiver_id)
        ]
        return "sha256:" + _canonical_hash(payload)

    @classmethod
    def performance_gate(
        cls,
        incumbent: PerformanceVector,
        candidate: PerformanceVector,
        *,
        tolerance: float = 1e-9,
    ) -> tuple[bool, float | None, tuple[str, ...]]:
        regressions: list[str] = []
        for field_name in cls.PROTECTED_POSITIVE:
            if getattr(candidate, field_name) + tolerance < getattr(incumbent, field_name):
                regressions.append(field_name)
        for field_name in cls.PROTECTED_COSTS:
            if getattr(candidate, field_name) > getattr(incumbent, field_name) + tolerance:
                regressions.append(field_name)

        baseline = fitness(incumbent)
        candidate_score = fitness(candidate)
        ratio = candidate_score / baseline if baseline > 0 else None
        gate = candidate_score > baseline and not regressions
        return gate, ratio, tuple(sorted(regressions))

    @staticmethod
    def _rank_hypotheses(hypotheses: Iterable[CausalHypothesis]) -> tuple[CausalHypothesis, ...]:
        def score(item: CausalHypothesis) -> float:
            confidence = max(0.0, min(1.0, item.confidence))
            information = max(0.0, item.expected_information_gain)
            cost = max(0.0, item.test_cost)
            return (confidence * information) / (1.0 + cost)

        return tuple(
            sorted(
                hypotheses,
                key=lambda item: (
                    not item.falsifiable,
                    -score(item),
                    -len(item.supporting_evidence),
                    len(item.conflicting_evidence),
                    item.hypothesis_id,
                ),
            )
        )

    @staticmethod
    def _default_hypotheses(observation: FailureObservation) -> tuple[CausalHypothesis, ...]:
        code = observation.failure_code.upper()
        return (
            CausalHypothesis(
                hypothesis_id="H-ROUTE",
                statement=f"The active route or transport is the primary cause of {code}.",
                confidence=0.34,
                falsification_test="Replay the smallest read-only equivalent through a materially different authorised route and compare stage timing plus semantic fruit.",
                predicted_if_true="The alternate route succeeds or fails at a different stage while the original route reproduces the defect.",
                expected_information_gain=0.9,
                test_cost=0.4,
            ),
            CausalHypothesis(
                hypothesis_id="H-DEPENDENCY",
                statement="A dependency, schema, configuration or stale binding is the primary cause.",
                confidence=0.33,
                falsification_test="Rebind current dependencies/configuration from live metadata, then rerun the failure-first fixture without changing mission semantics.",
                predicted_if_true="The failure disappears after exact-current binding while unchanged stale binding still fails.",
                expected_information_gain=0.85,
                test_cost=0.5,
            ),
            CausalHypothesis(
                hypothesis_id="H-AUTHORITY-SEMANTIC",
                statement="Authority/provider readiness or semantic mismatch, rather than transport, is the primary cause.",
                confidence=0.33,
                falsification_test="Separate transport health from action-specific authority and semantic readback using a bounded provider/action probe.",
                predicted_if_true="Transport may pass while authority or semantic readback fails independently.",
                expected_information_gain=0.8,
                test_cost=0.6,
            ),
        )

    @staticmethod
    def _oscillation(history: tuple[str, ...]) -> bool:
        compact = tuple(item for item in history if item)
        if len(compact) < 4:
            return False
        tail = compact[-4:]
        alternating = tail[0] == tail[2] and tail[1] == tail[3] and tail[0] != tail[1]
        repeated = len(set(compact[-3:])) == 1
        return alternating or repeated

    def _rank_routes(self, routes: Iterable[RecoveryRoute]) -> tuple[RecoveryRoute, ...]:
        eligible: list[tuple[RecoveryRoute, Route]] = []
        for item in routes:
            if not all(
                (
                    item.available,
                    item.authorised,
                    item.zero_or_included_cost,
                    item.rollback_available,
                    item.materially_different,
                )
            ):
                continue
            formation_route = Route(
                route_id=item.route_id,
                route_type=item.route_type,
                feasibility=max(0.0, 1.0 - item.expected_risk),
                proof_strength=item.proof_strength,
                reversibility=item.reversibility,
                speed=max(0.0, item.performance.speed),
                strategic_value=item.strategic_value + item.expected_value,
                owner_burden=max(0.0, item.performance.owner_burden),
                privacy_cost=max(0.0, item.performance.privacy_risk),
                maintenance_cost=max(0.0, item.performance.maintenance_cost + item.expected_cost),
            )
            eligible.append((item, formation_route))
        ranked_ids = [item.route_id for item in self.formation.rank([route for _, route in eligible])]
        by_id = {item.route_id: item for item, _ in eligible}
        return tuple(by_id[route_id] for route_id in ranked_ids)

    @staticmethod
    def _proof_graph(
        request: FailureWinRequest,
        *,
        vector_gate_passed: bool,
        selected_routes: tuple[RecoveryRoute, ...],
    ) -> ProofGraphAssessment:
        evidence = request.evidence
        required: dict[str, bool] = {
            "FAILURE_FACT_PRESERVED": evidence.failure_fact_preserved,
            "CAUSAL_MODEL_RECORDED": evidence.causal_model_recorded,
            "FALSIFICATION_EXECUTED": evidence.falsification_executed,
            "MATERIALLY_DIFFERENT_ROUTE": bool(selected_routes),
            "PERFORMANCE_VECTOR_GATE": vector_gate_passed,
            "AUTHORITY_CURRENT": evidence.authority_current,
            "COST_ALLOWED": evidence.cost_allowed,
            "FAILURE_FIRST_TEST": evidence.failure_first_test_passed,
            "HEALTHY_PATH_TEST": evidence.healthy_path_test_passed,
            "ROLLBACK_TEST": evidence.rollback_test_passed,
            "FORWARD_CANARY": evidence.forward_canary_passed,
            "INDEPENDENT_SEMANTIC_READBACK": evidence.independent_semantic_readback,
            "POSITIVE_VALUE": evidence.positive_value,
            "NO_REGRESSION": evidence.no_regression,
            "OWNER_BURDEN_NOT_INCREASED": evidence.owner_burden_not_increased,
        }
        if request.provider_dependent:
            required["PROVIDER_RECEIPT"] = evidence.provider_receipt_present
        if request.estate_scope_claim:
            receiver_ok = (
                request.receiver_manifest_complete
                and bool(request.receiver_attestations)
                and all(
                    item.kernel_invoked
                    and item.behavior_proven
                    and item.current
                    and item.independent_readback
                    and bool(item.evidence_refs)
                    for item in request.receiver_attestations
                )
            )
            required["DYNAMIC_RECEIVER_MANIFEST_COMPLETE"] = request.receiver_manifest_complete
            required["RECEIVER_NATIVE_BEHAVIOR_PROOF"] = receiver_ok
        satisfied = tuple(sorted(key for key, value in required.items() if value))
        missing = tuple(sorted(key for key, value in required.items() if not value))
        return ProofGraphAssessment(
            required_nodes=tuple(sorted(required)),
            satisfied_nodes=satisfied,
            missing_nodes=missing,
            complete=not missing,
        )

    @staticmethod
    def _bounded_win_ready(request: FailureWinRequest, graph: ProofGraphAssessment) -> bool:
        bounded_required = {
            "FAILURE_FACT_PRESERVED",
            "CAUSAL_MODEL_RECORDED",
            "FALSIFICATION_EXECUTED",
            "MATERIALLY_DIFFERENT_ROUTE",
            "PERFORMANCE_VECTOR_GATE",
            "AUTHORITY_CURRENT",
            "COST_ALLOWED",
            "FAILURE_FIRST_TEST",
            "HEALTHY_PATH_TEST",
            "ROLLBACK_TEST",
            "FORWARD_CANARY",
            "INDEPENDENT_SEMANTIC_READBACK",
            "POSITIVE_VALUE",
            "NO_REGRESSION",
            "OWNER_BURDEN_NOT_INCREASED",
        }
        if request.provider_dependent:
            bounded_required.add("PROVIDER_RECEIPT")
        return bounded_required.issubset(set(graph.satisfied_nodes))

    @staticmethod
    def _operational_win_ready(request: FailureWinRequest, graph: ProofGraphAssessment) -> bool:
        if not graph.complete:
            return False
        return (
            request.evidence.repeated_successes >= request.required_repeated_successes
            and request.evidence.soak_seconds >= request.required_soak_seconds
        )

    def evaluate(self, request: FailureWinRequest) -> FailureWinResult:
        observation = request.observation
        fingerprint = self.fingerprint(observation)
        portable_fingerprint = self.portable_fingerprint(observation)
        prior = self._genome.get(fingerprint)
        recurrence = max(observation.recurrence_count, (prior.recurrence + 1) if prior else 1)

        ranked_hypotheses = self._rank_hypotheses(request.hypotheses or self._default_hypotheses(observation))
        next_falsification = next(
            (item.falsification_test for item in ranked_hypotheses if item.falsifiable),
            "",
        )
        causal_ready = bool(ranked_hypotheses and next_falsification)

        time_breaches = tuple(sorted(item.stage for item in observation.stage_budgets if item.breached))
        oscillation = self._oscillation(observation.recent_route_history)

        ranked_routes = self._rank_routes(request.routes)
        route_candidates: list[RecoveryRoute] = []
        best_ratio: float | None = None
        regressions: set[str] = set()
        for route in ranked_routes:
            gate, ratio, protected = self.performance_gate(request.incumbent, route.performance)
            regressions.update(protected)
            if gate:
                route_candidates.append(route)
                if ratio is not None and (best_ratio is None or ratio > best_ratio):
                    best_ratio = ratio

        max_width = max(1, request.maximum_race_width)
        selected = tuple(route_candidates[:max_width])
        vector_gate = bool(selected)

        graph = self._proof_graph(request, vector_gate_passed=vector_gate, selected_routes=selected)
        manifest_hash = self.receiver_manifest_hash(request.receiver_attestations)

        horizon_run = self.horizon.simulate(
            objective=observation.objective or observation.desired_outcome,
            profile="FAILURE_TO_OPERATIONAL_WIN_V2",
            consequential=observation.material,
            consequence=0.9 if observation.material else 0.5,
            uncertainty=0.8 if not causal_ready else 0.5,
            dependency_density=0.8 if request.estate_scope_claim else 0.5,
            adversarial_complexity=0.7,
            immediate_response="Failed route remains quarantined while materially different candidates are evaluated",
            strongest_pivot="Use a different authorized recovery path with stronger proof and lower owner burden",
            decision_maker_response="Require exact failure, causal, regression, rollback, readback and value proof before promotion",
            cross_lane_risks=("common-mode failure", "repair oscillation", "receiver drift", "proof inheritance"),
            fallback="Preserve the objective and verified state; isolate the failed lane and recompute",
            requested_depth=50 if observation.material else 12,
        )

        if oscillation:
            state = FailureWinState.QUARANTINED
            action = RecoveryAction.QUARANTINE
        elif self._operational_win_ready(request, graph):
            state = FailureWinState.OPERATIONAL_WIN_VERIFIED
            action = RecoveryAction.OBSERVE
        elif self._bounded_win_ready(request, graph):
            state = FailureWinState.BOUNDED_WIN
            action = RecoveryAction.OBSERVE
        elif observation.event_type == FailureEventType.PRECURSOR_RISK and selected:
            state = FailureWinState.PREEMPTION_READY
            action = RecoveryAction.PREEMPT
        elif observation.material:
            if selected and causal_ready:
                state = FailureWinState.ROUTE_SELECTED
                action = RecoveryAction.RACE_CANDIDATES if len(selected) > 1 else RecoveryAction.PATCH_EXISTING
            else:
                state = FailureWinState.REPAIR_CYCLE_OPEN
                action = RecoveryAction.OBSERVE
        else:
            state = FailureWinState.OBSERVE
            action = RecoveryAction.OBSERVE

        quarantined_routes = set(prior.quarantined_routes if prior else ())
        if observation.failed_route_id:
            quarantined_routes.add(observation.failed_route_id)
        if oscillation:
            quarantined_routes.update(observation.recent_route_history[-4:])
        self._genome[fingerprint] = FailureGenomeRecord(
            fingerprint=fingerprint,
            failure_code=observation.failure_code,
            system_id=observation.system_id,
            first_event_id=prior.first_event_id if prior else observation.event_id,
            recurrence=recurrence,
            last_state=state.value,
            quarantined_routes=tuple(sorted(quarantined_routes)),
        )

        prewarm = tuple(
            route.route_id
            for route in selected
            if route.provider_neutral or (route.authorised and route.rollback_available)
        )

        next_actions: list[str] = []
        if not causal_ready:
            next_actions.append("FORM_AND_FALSIFY_COMPETING_CAUSAL_HYPOTHESES")
        if not selected and observation.material:
            next_actions.append("SEARCH_DYNAMIC_CAPABILITY_GRAPH_FOR_MATERIALLY_DIFFERENT_ROUTE")
        if time_breaches:
            if any(item.breached and item.hard_commitment for item in observation.stage_budgets):
                next_actions.append("PRESERVE_HARD_TIME_COMMITMENT_AND_PREWARM_OR_REROUTE_SLOW_DEPENDENCIES")
            else:
                next_actions.append("REBASE_STAGE_SPECIFIC_TIME_BUDGET_FROM_OBSERVED_DATA_AND_PREWARM_SLOW_DEPENDENCIES")
        if oscillation:
            next_actions.append("QUARANTINE_THRASHING_ROUTES_AND_FORCE_NEW_RECOVERY_CLASS")
        if graph.missing_nodes:
            next_actions.append("CLOSE_PROOF_GRAPH:" + ",".join(graph.missing_nodes))
        if state == FailureWinState.BOUNDED_WIN:
            next_actions.append("RUN_REPEATED_FORWARD_CANARIES_AND_SOAK_BEFORE_OPERATIONAL_PROMOTION")
        if request.estate_scope_claim and not request.receiver_manifest_complete:
            next_actions.append("REGENERATE_DYNAMIC_RECEIVER_MANIFEST_FROM_CURRENT_FEDERATION_REGISTRY")
        if state == FailureWinState.OPERATIONAL_WIN_VERIFIED:
            next_actions.append("DIFFUSE_PROVEN_PROVIDER_NEUTRAL_LEARNING_AND_OPEN_PREVENTION_CYCLE")
        if not next_actions:
            next_actions.append("PRESERVE_CURRENT_STATE_AND_CONTINUE_MEASURED_OBSERVATION")

        adaptive_budget_suggestions = {
            item.stage: round(max(item.budget_seconds, (item.observed_seconds or 0.0) * 1.2), 3)
            for item in observation.stage_budgets
            if item.breached and not item.hard_commitment
        }
        kpis = {
            "portable_failure_fingerprint": portable_fingerprint,
            "mttr_target_seconds": sum(item.budget_seconds for item in observation.stage_budgets)
            if observation.stage_budgets
            else None,
            "time_budget_breach_count": len(time_breaches),
            "route_candidates_evaluated": len(tuple(request.routes)),
            "eligible_race_width": len(selected),
            "failure_recurrence": recurrence,
            "proof_nodes_satisfied": len(graph.satisfied_nodes),
            "proof_nodes_required": len(graph.required_nodes),
            "repeated_successes": request.evidence.repeated_successes,
            "soak_seconds": request.evidence.soak_seconds,
            "owner_burden_delta": observation.owner_burden_delta,
            "prevention_signals": len(observation.precursor_signals),
            "adaptive_budget_suggestions": adaptive_budget_suggestions,
        }

        return FailureWinResult(
            kernel=self.KERNEL_ID,
            version=self.VERSION,
            state=state,
            action=action,
            fingerprint=fingerprint,
            portable_fingerprint=portable_fingerprint,
            recurrence=recurrence,
            selected_route_ids=tuple(item.route_id for item in selected),
            ranked_hypothesis_ids=tuple(item.hypothesis_id for item in ranked_hypotheses),
            next_falsification_test=next_falsification,
            vector_gate_passed=vector_gate,
            measured_fitness_ratio=best_ratio,
            protected_regressions=tuple(sorted(regressions)),
            time_budget_breaches=time_breaches,
            oscillation_detected=oscillation,
            receiver_manifest_hash=manifest_hash,
            proof_graph=graph,
            prewarm_route_ids=prewarm,
            horizon_depth=horizon_run.adaptive_depth,
            kpis=kpis,
            next_actions=tuple(next_actions),
            truth_boundary=(
                "This result is a deterministic closed-loop recovery and proof decision. "
                "It does not itself execute provider mutations, grant authority, prove a "
                "receiver runtime binding, or establish estate-wide operational maturity. "
                "OPERATIONAL_WIN_VERIFIED is emitted only when the supplied evidence graph, "
                "repeated-success/soak thresholds and any requested receiver-native attestations pass."
            ),
        )

    def observe_federation_event(self, event: FederationEvent) -> dict[str, Any]:
        event_type_map = {
            "TOOL_FAILURE": FailureEventType.FAILURE,
            "FAILURE": FailureEventType.FAILURE,
            "TIMEOUT": FailureEventType.TIMEOUT,
            "REGRESSION": FailureEventType.REGRESSION,
            "CLAIM_FRUIT_CONTRADICTION": FailureEventType.CLAIM_FRUIT_CONTRADICTION,
            "PROVIDER_ERROR": FailureEventType.PROVIDER_ERROR,
            "OWNER_CORRECTION": FailureEventType.OWNER_CORRECTION,
            "SLO_BREACH": FailureEventType.SLO_BREACH,
            "CANARY_FAILURE": FailureEventType.CANARY_FAILURE,
            "PRECURSOR_RISK": FailureEventType.PRECURSOR_RISK,
        }
        event_type = event_type_map.get(event.event_type, FailureEventType.FAILURE)
        payload = event.payload
        request = FailureWinRequest(
            observation=FailureObservation(
                event_id=event.event_id,
                event_type=event_type,
                system_id=event.source or "UNKNOWN",
                objective=str(payload.get("objective", event.workstream or "Preserve owner objective")),
                claim=str(payload.get("claim", "Material operation should produce the requested fruit")),
                observed_fruit=str(payload.get("observed_fruit", payload.get("error", event.event_type))),
                desired_outcome=str(payload.get("desired_outcome", payload.get("objective", "Operational completion"))),
                failure_code=str(payload.get("failure_code", payload.get("failure_type", event.event_type))),
                provider=str(payload.get("provider", "")),
                configuration_hash=str(payload.get("configuration_hash", "")),
                dependency_refs=tuple(map(str, payload.get("dependency_refs", ()) or ())),
                failed_route_id=str(payload.get("route_id", "")),
                material=bool(payload.get("material", event_type != FailureEventType.PRECURSOR_RISK)),
                recurrence_count=int(payload.get("recurrence_count", 1)),
                owner_burden_delta=float(payload.get("owner_burden_delta", 0.0)),
                precursor_signals=tuple(map(str, payload.get("precursor_signals", ()) or ())),
                recent_route_history=tuple(map(str, payload.get("recent_route_history", ()) or ())),
            )
        )
        return self.evaluate(request).to_dict()

    def genome_snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(self._genome[key]) for key in sorted(self._genome))
