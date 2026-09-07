"""FUSE Ω — Autonomous Algorithm Assurance, Learning & Evolution Kernel (AAREK) v1.1.

Provider-neutral, effect-free orchestration kernel. AAREK does not execute provider
effects itself and does not create an authority plane, scheduler, truth store, proof
store, memory root, or provider runtime. It evaluates supplied evidence and emits
deterministic next-action/assurance receipts for an existing mission orchestrator.

Canonical role:
Owner Protection → AAREK → OH50 → Formation Innovation → Alpha→Omega (if build
is required) → execution → action-specific semantic readback → Failure-Win /
Route Memory / Regression Lab → mission recompile → COMPLETE_VERIFIED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

CAPABILITY_ID = "FUSE-AAREK-V1.1"
SCHEMA = "FUSE-AAREK-ASSURANCE-V1.1"
VERSION = "1.1.0"


class Authority(str, Enum):
    A0_INTERNAL = "A0_INTERNAL"
    A1_INTERNAL = "A1_INTERNAL"
    A2_OWNER_RESERVED = "A2_OWNER_RESERVED"


_AUTHORITY_RANK = {
    Authority.A0_INTERNAL.value: 0,
    Authority.A1_INTERNAL.value: 1,
    Authority.A2_OWNER_RESERVED.value: 2,
}


class EvidenceKind(str, Enum):
    DESIGN = "DESIGN"
    SOURCE = "SOURCE"
    TEST = "TEST"
    CI = "CI"
    QUEUE = "QUEUE"
    SCHEDULE = "SCHEDULE"
    HEARTBEAT = "HEARTBEAT"
    GENERIC_HTTP = "GENERIC_HTTP"
    BINDING = "BINDING"
    EXECUTION = "EXECUTION"
    PROVIDER_ACK = "PROVIDER_ACK"
    PROVIDER_RESPONSE = "PROVIDER_RESPONSE"
    PROVIDER_RECEIPT = "PROVIDER_RECEIPT"
    SEMANTIC_READBACK = "SEMANTIC_READBACK"
    REGRESSION = "REGRESSION"
    VALUE = "VALUE"


_NON_EXECUTION_KINDS = {
    EvidenceKind.DESIGN,
    EvidenceKind.SOURCE,
    EvidenceKind.TEST,
    EvidenceKind.CI,
    EvidenceKind.QUEUE,
    EvidenceKind.SCHEDULE,
    EvidenceKind.HEARTBEAT,
    EvidenceKind.GENERIC_HTTP,
}


class AarekState(str, Enum):
    REGISTERED = "REGISTERED"
    BINDING_REQUIRED = "BINDING_REQUIRED"
    RUNNABLE = "RUNNABLE"
    EXECUTION_REQUIRED = "EXECUTION_REQUIRED"
    READBACK_REQUIRED = "READBACK_REQUIRED"
    FAILURE_CLASSIFIED = "FAILURE_CLASSIFIED"
    CHANGED_ROUTE_REQUIRED = "CHANGED_ROUTE_REQUIRED"
    CHALLENGER_SELECTED = "CHALLENGER_SELECTED"
    REGRESSION_REQUIRED = "REGRESSION_REQUIRED"
    VALUE_REQUIRED = "VALUE_REQUIRED"
    WIN_VERIFIED = "WIN_VERIFIED"
    IMPROVEMENT_SPAWNED = "IMPROVEMENT_SPAWNED"
    MISSION_RECOMPILED = "MISSION_RECOMPILED"
    COMPLETE_VERIFIED = "COMPLETE_VERIFIED"
    HELD_OWNER_ONLY = "HELD_OWNER_ONLY"


class Decision(str, Enum):
    ACQUIRE_BINDING = "ACQUIRE_BINDING"
    EXECUTE = "EXECUTE"
    REQUIRE_SEMANTIC_READBACK = "REQUIRE_SEMANTIC_READBACK"
    PRESERVE_AND_CLASSIFY_FAILURE = "PRESERVE_AND_CLASSIFY_FAILURE"
    CHALLENGE_ROUTES = "CHALLENGE_ROUTES"
    SELECT_CHALLENGER = "SELECT_CHALLENGER"
    RUN_REGRESSION = "RUN_REGRESSION"
    MEASURE_VALUE = "MEASURE_VALUE"
    CAPTURE_WIN_AND_SPAWN_IMPROVEMENT = "CAPTURE_WIN_AND_SPAWN_IMPROVEMENT"
    RECOMPILE_MISSION = "RECOMPILE_MISSION"
    CONTINUE_MISSION = "CONTINUE_MISSION"
    ALLOW_COMPLETE_VERIFIED = "ALLOW_COMPLETE_VERIFIED"
    HOLD_OWNER_ONLY = "HOLD_OWNER_ONLY"


class RegressionCode(str, Enum):
    ADVICE_WITHOUT_EXECUTION = "ADVICE_WITHOUT_EXECUTION"
    SCHEDULER_SURFACE_SUBSTITUTION = "SCHEDULER_SURFACE_SUBSTITUTION"
    PREMATURE_PROGRESS_SIGNAL = "PREMATURE_PROGRESS_SIGNAL"
    UNCHANGED_ROUTE_RETRY = "UNCHANGED_ROUTE_RETRY"
    SEMANTIC_READBACK_MISSING = "SEMANTIC_READBACK_MISSING"
    OWNER_OFFLOAD_WHILE_MACHINE_ROUTE_EXISTS = "OWNER_OFFLOAD_WHILE_MACHINE_ROUTE_EXISTS"
    SOURCE_CI_PROMOTED_TO_RUNTIME = "SOURCE_CI_PROMOTED_TO_RUNTIME"
    COMPLETE_WITH_OPEN_MISSION_DEBT = "COMPLETE_WITH_OPEN_MISSION_DEBT"
    AUTHORITY_WIDENING = "AUTHORITY_WIDENING"


@dataclass(frozen=True, slots=True)
class Evidence:
    kind: EvidenceKind
    ref: str
    action_specific: bool = False
    provider_native: bool = False
    substantive: bool = False

    def valid(self) -> bool:
        return bool(self.ref.strip())


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    route_id: str
    eligible: bool = True
    callable_now: bool = False
    correctness: float = 0.0
    proof_strength: float = 0.0
    semantic_readback: float = 0.0
    success_probability: float = 0.0
    latency_score: float = 0.0
    durability: float = 0.0
    recovery: float = 0.0
    reversibility: float = 0.0
    failure_domain_diversity: float = 0.0
    authority_fit: float = 0.0
    owner_burden_inverse: float = 0.0
    information_gain: float = 0.0

    def score(self) -> float:
        if not self.eligible or not self.route_id.strip():
            return float("-inf")
        weighted = (
            2.0 * self.correctness
            + 2.0 * self.proof_strength
            + 2.0 * self.semantic_readback
            + 1.5 * self.success_probability
            + self.latency_score
            + self.durability
            + self.recovery
            + self.reversibility
            + self.failure_domain_diversity
            + self.authority_fit
            + self.owner_burden_inverse
            + self.information_gain
        )
        if self.callable_now:
            weighted += 0.5
        return round(weighted, 6)


@dataclass(frozen=True, slots=True)
class MissionSnapshot:
    mission_id: str
    objective: str
    authority_ceiling: str = Authority.A1_INTERNAL.value
    evidence: tuple[Evidence, ...] = ()
    required_terminal_predicates: tuple[str, ...] = ()
    satisfied_terminal_predicates: tuple[str, ...] = ()
    failure_fingerprint: str = ""
    prior_failure_fingerprint: str = ""
    failure_predicate_changed: bool = False
    selected_route_id: str = ""
    prior_route_id: str = ""
    route_candidates: tuple[RouteCandidate, ...] = ()
    regression_required: bool = False
    regression_passed: bool = False
    value_required: bool = False
    value_measured: bool = False
    verified_win: bool = False
    improvement_spawned: bool = False
    mission_recompiled: bool = False
    owner_only_boundary: str = ""
    machine_routes_exhausted: bool = False
    owner_offload_proposed: bool = False


@dataclass(frozen=True, slots=True)
class AarekReceipt:
    schema: str
    capability_id: str
    version: str
    mission_id: str
    state: AarekState
    decision: Decision
    selected_route_id: str
    regressions: tuple[str, ...]
    proof_refs: tuple[str, ...]
    terminal_debt: tuple[str, ...]
    auto_continue_required: bool
    owner_surface_allowed: bool
    provider_runtime_proven: bool
    receipt_digest: str


def _authority_within(child: str, parent: str) -> bool:
    return child in _AUTHORITY_RANK and parent in _AUTHORITY_RANK and _AUTHORITY_RANK[child] <= _AUTHORITY_RANK[parent]


def _digest(value: Mapping[str, object]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


class AarekKernel:
    """Deterministic assurance/learning decision kernel over supplied mission evidence."""

    def evaluate(self, snapshot: MissionSnapshot) -> AarekReceipt:
        self._validate(snapshot)
        evidence = tuple(item for item in snapshot.evidence if item.valid())
        evidence_kinds = {item.kind for item in evidence}
        regressions: list[str] = []

        binding = any(item.kind is EvidenceKind.BINDING and item.action_specific for item in evidence)
        execution = any(item.kind is EvidenceKind.EXECUTION and item.action_specific for item in evidence)
        semantic_readback = any(item.kind is EvidenceKind.SEMANTIC_READBACK and item.action_specific for item in evidence)
        provider_runtime_proven = any(
            item.provider_native
            and item.kind in {
                EvidenceKind.EXECUTION,
                EvidenceKind.PROVIDER_ACK,
                EvidenceKind.PROVIDER_RESPONSE,
                EvidenceKind.PROVIDER_RECEIPT,
                EvidenceKind.SEMANTIC_READBACK,
            }
            for item in evidence
        )

        required = set(snapshot.required_terminal_predicates)
        satisfied = set(snapshot.satisfied_terminal_predicates)
        terminal_debt = tuple(sorted(required - satisfied))

        only_non_execution = bool(evidence) and all(item.kind in _NON_EXECUTION_KINDS for item in evidence)
        if only_non_execution and (binding or execution or semantic_readback):
            raise AssertionError("unreachable")
        if only_non_execution and not terminal_debt:
            regressions.append(RegressionCode.SOURCE_CI_PROMOTED_TO_RUNTIME.value)

        unchanged_retry = bool(
            snapshot.failure_fingerprint.strip()
            and snapshot.failure_fingerprint == snapshot.prior_failure_fingerprint
            and not snapshot.failure_predicate_changed
            and snapshot.selected_route_id
            and snapshot.selected_route_id == snapshot.prior_route_id
        )
        if unchanged_retry:
            regressions.append(RegressionCode.UNCHANGED_ROUTE_RETRY.value)

        if snapshot.owner_offload_proposed and not snapshot.machine_routes_exhausted:
            regressions.append(RegressionCode.OWNER_OFFLOAD_WHILE_MACHINE_ROUTE_EXISTS.value)

        selected = self._best_route(snapshot.route_candidates)

        if not binding:
            state = AarekState.BINDING_REQUIRED
            decision = Decision.ACQUIRE_BINDING
        elif not execution:
            state = AarekState.EXECUTION_REQUIRED
            decision = Decision.EXECUTE
            if EvidenceKind.SCHEDULE in evidence_kinds or EvidenceKind.QUEUE in evidence_kinds:
                regressions.append(RegressionCode.SCHEDULER_SURFACE_SUBSTITUTION.value)
        elif not semantic_readback:
            state = AarekState.READBACK_REQUIRED
            decision = Decision.REQUIRE_SEMANTIC_READBACK
            regressions.append(RegressionCode.SEMANTIC_READBACK_MISSING.value)
        elif snapshot.failure_fingerprint.strip():
            if unchanged_retry:
                state = AarekState.CHANGED_ROUTE_REQUIRED
                decision = Decision.CHALLENGE_ROUTES
            elif selected and selected.route_id != snapshot.selected_route_id:
                state = AarekState.CHALLENGER_SELECTED
                decision = Decision.SELECT_CHALLENGER
            else:
                state = AarekState.FAILURE_CLASSIFIED
                decision = Decision.CHALLENGE_ROUTES
        elif snapshot.regression_required and not snapshot.regression_passed:
            state = AarekState.REGRESSION_REQUIRED
            decision = Decision.RUN_REGRESSION
        elif snapshot.value_required and not snapshot.value_measured:
            state = AarekState.VALUE_REQUIRED
            decision = Decision.MEASURE_VALUE
        elif snapshot.verified_win and not snapshot.improvement_spawned:
            state = AarekState.WIN_VERIFIED
            decision = Decision.CAPTURE_WIN_AND_SPAWN_IMPROVEMENT
        elif snapshot.improvement_spawned and not snapshot.mission_recompiled:
            state = AarekState.IMPROVEMENT_SPAWNED
            decision = Decision.RECOMPILE_MISSION
        elif terminal_debt:
            state = AarekState.MISSION_RECOMPILED if snapshot.mission_recompiled else AarekState.RUNNABLE
            decision = Decision.CONTINUE_MISSION
        elif snapshot.owner_only_boundary.strip() and snapshot.machine_routes_exhausted:
            state = AarekState.HELD_OWNER_ONLY
            decision = Decision.HOLD_OWNER_ONLY
        elif snapshot.mission_recompiled and semantic_readback and execution and binding:
            state = AarekState.COMPLETE_VERIFIED
            decision = Decision.ALLOW_COMPLETE_VERIFIED
        else:
            state = AarekState.MISSION_RECOMPILED
            decision = Decision.RECOMPILE_MISSION

        if decision is Decision.ALLOW_COMPLETE_VERIFIED and terminal_debt:
            regressions.append(RegressionCode.COMPLETE_WITH_OPEN_MISSION_DEBT.value)

        owner_surface_allowed = decision in {Decision.ALLOW_COMPLETE_VERIFIED, Decision.HOLD_OWNER_ONLY}
        auto_continue_required = not owner_surface_allowed

        proof_refs = tuple(sorted({item.ref.strip() for item in evidence if item.ref.strip()}))
        material = {
            "schema": SCHEMA,
            "capability_id": CAPABILITY_ID,
            "version": VERSION,
            "mission_id": snapshot.mission_id,
            "state": state.value,
            "decision": decision.value,
            "selected_route_id": selected.route_id if selected else "",
            "regressions": sorted(set(regressions)),
            "proof_refs": proof_refs,
            "terminal_debt": terminal_debt,
            "auto_continue_required": auto_continue_required,
            "owner_surface_allowed": owner_surface_allowed,
            "provider_runtime_proven": provider_runtime_proven,
        }
        return AarekReceipt(
            schema=SCHEMA,
            capability_id=CAPABILITY_ID,
            version=VERSION,
            mission_id=snapshot.mission_id,
            state=state,
            decision=decision,
            selected_route_id=selected.route_id if selected else "",
            regressions=tuple(sorted(set(regressions))),
            proof_refs=proof_refs,
            terminal_debt=terminal_debt,
            auto_continue_required=auto_continue_required,
            owner_surface_allowed=owner_surface_allowed,
            provider_runtime_proven=provider_runtime_proven,
            receipt_digest=_digest(material),
        )

    @staticmethod
    def _best_route(routes: Sequence[RouteCandidate]) -> RouteCandidate | None:
        eligible = [route for route in routes if route.eligible and route.route_id.strip()]
        if not eligible:
            return None
        return max(eligible, key=lambda route: (route.score(), route.route_id))

    @staticmethod
    def _validate(snapshot: MissionSnapshot) -> None:
        if not snapshot.mission_id.strip():
            raise ValueError("MISSION_ID_REQUIRED")
        if not snapshot.objective.strip():
            raise ValueError("OBJECTIVE_REQUIRED")
        if snapshot.authority_ceiling not in _AUTHORITY_RANK:
            raise ValueError("UNKNOWN_AUTHORITY_CEILING")
        if len(snapshot.required_terminal_predicates) != len(set(snapshot.required_terminal_predicates)):
            raise ValueError("DUPLICATE_TERMINAL_PREDICATE")
        if not set(snapshot.satisfied_terminal_predicates).issubset(set(snapshot.required_terminal_predicates)):
            raise ValueError("SATISFIED_PREDICATE_NOT_REQUIRED")
        for route in snapshot.route_candidates:
            if not _authority_within(Authority.A1_INTERNAL.value, snapshot.authority_ceiling):
                raise ValueError(RegressionCode.AUTHORITY_WIDENING.value)
