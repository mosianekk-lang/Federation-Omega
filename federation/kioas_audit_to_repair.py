from __future__ import annotations

"""KIOAS Audit-to-Repair Compiler (ARC) v1.

Provider-neutral, deterministic control logic that turns material audit findings
into bounded repair transactions. ARC does not execute provider effects, own a
scheduler, or self-certify repairs. It reuses existing Federation execution,
proof, rollback, learning, and scheduling planes.
"""

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "KIOAS-AUDIT-TO-REPAIR-COMPILER-V1"
VERSION = "1.0.0"
AUTHORITY_CEILING = "A1_INTERNAL"
CFBE_BENCHMARK_REFS = (
    "P-012",  # AgentOps: governance/build/eval/observability
    "P-017",  # incident -> diagnosis -> repair -> learning
    "P-022",  # bounded failure domains
    "P-023",  # progressive promotion rings
    "P-024",  # desired/current reconciliation
    "P-025",  # shared-state concurrency/idempotency
    "P-033",  # failure/trajectory mining into experiments
    "P-011",  # durable resumable steps
    "PAT-HSO-OMEGA-001",
    "PAT-CFBE-VIRT100-001",
)


class RepairClass(str, Enum):
    AUTO_REPAIR_NOW = "AUTO_REPAIR_NOW"
    AUTO_REPAIR_FENCED = "AUTO_REPAIR_FENCED"
    AUTO_REPAIR_CANARY = "AUTO_REPAIR_CANARY"
    WAITING_EXACT_CAPABILITY = "WAITING_EXACT_CAPABILITY"
    OWNER_OR_PROVIDER_TRIGGER_REQUIRED = "OWNER_OR_PROVIDER_TRIGGER_REQUIRED"
    QUARANTINE_AND_REROUTE = "QUARANTINE_AND_REROUTE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REJECTED_WITH_EVIDENCE = "REJECTED_WITH_EVIDENCE"


class TransactionState(str, Enum):
    COMPILED = "COMPILED"
    READY = "READY"
    WAITING = "WAITING"
    QUARANTINED = "QUARANTINED"
    APPLIED_UNVERIFIED = "APPLIED_UNVERIFIED"
    REPAIRED_VERIFIED = "REPAIRED_VERIFIED"
    HELD_EXACT_GATE = "HELD_EXACT_GATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REJECTED_WITH_EVIDENCE = "REJECTED_WITH_EVIDENCE"


TERMINAL_STATES = frozenset(
    {
        TransactionState.REPAIRED_VERIFIED,
        TransactionState.HELD_EXACT_GATE,
        TransactionState.NOT_APPLICABLE,
        TransactionState.REJECTED_WITH_EVIDENCE,
    }
)


@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    objective: str
    observed_state: str
    desired_state: str
    severity: float = 1.0
    strategic_weight: float = 1.0
    blast_radius: float = 1.0
    recurrence_risk: float = 1.0
    dependency_unlock: float = 1.0
    owner_burden_reduction: float = 1.0
    feasibility: float = 1.0
    confidence: float = 1.0
    cost: float = 0.0
    irreversibility: float = 0.0
    authority_gap: float = 0.0
    collision_risk: float = 0.0
    material: bool = True
    prohibited: bool = False
    consequential_external_effect: bool = False
    exact_provider_or_owner_trigger: bool = False
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepairRoute:
    route_id: str
    route_kind: str
    summary: str
    callable_now: bool
    reversible: bool
    zero_or_included_cost: bool
    within_a1_authority: bool
    requires_shared_state_fence: bool = False
    requires_canary: bool = False
    independent_readback_available: bool = True
    rollback_available: bool = True
    proof_strength: float = 1.0
    freshness: float = 1.0
    reliability: float = 1.0
    dependency_unlock: float = 1.0
    owner_burden_reduction: float = 1.0
    information_gain: float = 1.0
    latency_penalty: float = 0.0
    maintenance_burden: float = 0.0
    collision_risk: float = 0.0
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepairHypothesis:
    primary_cause: str
    counter_hypothesis: str
    discriminating_test: str
    expected_result: str
    falsification_condition: str


@dataclass(frozen=True)
class RepairTransaction:
    transaction_id: str
    finding_id: str
    repair_class: RepairClass
    state: TransactionState
    priority_score: float
    selected_route_id: str | None
    route_rankings: tuple[tuple[str, float], ...]
    hypothesis: RepairHypothesis
    failure_fingerprint: str
    source_epoch: str
    authority_state: str
    failure_semantics: str
    repeated_unchanged_failure: bool
    required_preconditions: tuple[str, ...]
    proof_gates: tuple[str, ...]
    rollback_required: bool
    resume_trigger: str | None
    ledger_targets: tuple[str, ...]
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect_authorized: bool = False
    self_certification_allowed: bool = False
    executor_id: str | None = None
    execution_ref: str | None = None
    verifier_id: str | None = None
    verification_ref: str | None = None
    cfbe_prepass_ref: str = ""
    benchmark_refs: tuple[str, ...] = CFBE_BENCHMARK_REFS
    receipt_sha256: str = field(default="")


@dataclass(frozen=True)
class RepairExecutionPacket:
    schema: str
    transaction_id: str
    finding_id: str
    selected_route_id: str
    repair_class: str
    source_epoch: str
    authority_state: str
    failure_fingerprint: str
    idempotency_key: str
    required_preconditions: tuple[str, ...]
    proof_gates: tuple[str, ...]
    rollback_required: bool
    executor_contract: str = "FEDERATION_EXECUTION_MESH"
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect_authorized: bool = False
    provider_effect_authorized: bool = False
    self_certification_allowed: bool = False
    receipt_sha256: str = ""


@dataclass(frozen=True)
class ResumePacket:
    schema: str
    transaction_id: str
    finding_id: str
    transaction_state: str
    repair_class: str
    source_epoch: str
    authority_state: str
    resume_trigger: str
    scheduler_surface: str = "GOOGLE_APPS_SCRIPT_GNS3"
    chatgpt_scheduler_allowed: bool = False
    affected_controller_only: bool = True
    external_effect_authorized: bool = False
    receipt_sha256: str = ""



@dataclass(frozen=True)
class CandidateArtifactIdentity:
    schema: str
    logical_name: str
    version: str
    sha256: str
    size_bytes: int
    immutable_file_name: str
    source_epoch: str
    write_mode: str = "CREATE_IMMUTABLE_CANDIDATE"
    canonical_pointer_mutation: str = "COMPARE_AND_SET_ONLY"
    delete_superseded: bool = False
    receipt_sha256: str = ""


@dataclass(frozen=True)
class CanonicalPointerDecision:
    state: str
    observed_sha256: str
    expected_observed_sha256: str
    candidate_sha256: str
    mutation_allowed: bool
    requires_fresh_readback: bool = True
    delete_superseded: bool = False
    receipt_sha256: str = ""


@dataclass(frozen=True)
class VerificationResult:
    verifier_id: str
    verification_ref: str
    semantic_readback: bool
    independent_assurance: bool
    regression_pass: bool
    rollback_valid: bool
    authority_preserved: bool
    cost_preserved: bool
    value_positive_or_justified: bool
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuditTerminality:
    state: str
    executable_open: int
    applied_unverified: int
    held_exact_gate: int
    repaired_verified: int
    terminal_count: int
    total_count: int


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _bounded_nonnegative(value: float, field_name: str) -> float:
    number = float(value)
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field_name.upper()}_MUST_BE_FINITE_NONNEGATIVE")
    return number


def _require_text(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name.upper()}_REQUIRED")
    return text


def finding_priority(finding: AuditFinding) -> float:
    """CFBE-derived priority: value/unlock/risk over cost/irreversibility/gaps."""
    numerators = (
        _bounded_nonnegative(finding.severity, "severity"),
        _bounded_nonnegative(finding.strategic_weight, "strategic_weight"),
        _bounded_nonnegative(finding.blast_radius, "blast_radius"),
        _bounded_nonnegative(finding.recurrence_risk, "recurrence_risk"),
        _bounded_nonnegative(finding.dependency_unlock, "dependency_unlock"),
        _bounded_nonnegative(finding.owner_burden_reduction, "owner_burden_reduction"),
        _bounded_nonnegative(finding.feasibility, "feasibility"),
        _bounded_nonnegative(finding.confidence, "confidence"),
    )
    numerator = 1.0
    for value in numerators:
        numerator *= value
    denominator = 1.0 + sum(
        (
            _bounded_nonnegative(finding.cost, "cost"),
            _bounded_nonnegative(finding.irreversibility, "irreversibility"),
            _bounded_nonnegative(finding.authority_gap, "authority_gap"),
            _bounded_nonnegative(finding.collision_risk, "collision_risk"),
        )
    )
    return round(numerator / denominator, 8)


_KIND_BONUS = {
    "REUSE": 1.40,
    "EXTEND": 1.25,
    "REPURPOSE": 1.15,
    "COMPOSE": 1.05,
    "BUILD": 0.90,
}


def route_score(route: RepairRoute) -> float:
    kind = str(route.route_kind).strip().upper()
    if kind not in _KIND_BONUS:
        raise ValueError("ROUTE_KIND_MUST_BE_REUSE_EXTEND_REPURPOSE_COMPOSE_BUILD")
    if not route.rollback_available or not route.independent_readback_available:
        return -1.0
    positive = (
        _KIND_BONUS[kind]
        * _bounded_nonnegative(route.proof_strength, "proof_strength")
        * _bounded_nonnegative(route.freshness, "freshness")
        * _bounded_nonnegative(route.reliability, "reliability")
        * _bounded_nonnegative(route.dependency_unlock, "dependency_unlock")
        * _bounded_nonnegative(route.owner_burden_reduction, "owner_burden_reduction")
        * _bounded_nonnegative(route.information_gain, "information_gain")
    )
    penalty = 1.0 + sum(
        (
            _bounded_nonnegative(route.latency_penalty, "latency_penalty"),
            _bounded_nonnegative(route.maintenance_burden, "maintenance_burden"),
            _bounded_nonnegative(route.collision_risk, "collision_risk"),
        )
    )
    return round(positive / penalty, 8)


def rank_routes(routes: Sequence[RepairRoute]) -> tuple[tuple[str, float], ...]:
    seen: set[str] = set()
    ranked: list[tuple[str, float]] = []
    for route in routes:
        rid = _require_text(route.route_id, "route_id")
        if rid in seen:
            raise ValueError("DUPLICATE_ROUTE_ID")
        seen.add(rid)
        ranked.append((rid, route_score(route)))
    return tuple(sorted(ranked, key=lambda item: (-item[1], item[0])))


def failure_fingerprint(
    finding: AuditFinding,
    route: RepairRoute | None,
    *,
    source_epoch: str,
    authority_state: str,
    failure_semantics: str,
) -> str:
    payload = {
        "finding_id": _require_text(finding.finding_id, "finding_id"),
        "route_id": None if route is None else route.route_id,
        "source_epoch": _require_text(source_epoch, "source_epoch"),
        "authority_state": _require_text(authority_state, "authority_state"),
        "failure_semantics": _require_text(failure_semantics, "failure_semantics"),
    }
    return _digest(payload)


def _default_hypothesis(finding: AuditFinding) -> RepairHypothesis:
    return RepairHypothesis(
        primary_cause=f"Observed state diverges from desired state for {finding.finding_id}",
        counter_hypothesis="The apparent defect is stale observation, wrong target identity, or non-causal correlation",
        discriminating_test="Re-read target identity/state and run the smallest failure-first semantic canary",
        expected_result="The selected cause uniquely explains the observed divergence and predicts the canary result",
        falsification_condition="Fresh target-native readback contradicts the cause or the repair does not change the expected semantic outcome",
    )


def compile_finding(
    finding: AuditFinding,
    routes: Sequence[RepairRoute],
    *,
    source_epoch: str,
    authority_state: str,
    failure_semantics: str,
    prior_failure_fingerprints: Iterable[str] = (),
    hypothesis: RepairHypothesis | None = None,
    cfbe_prepass_ref: str = "",
) -> RepairTransaction:
    _require_text(finding.finding_id, "finding_id")
    _require_text(finding.objective, "objective")
    _require_text(finding.observed_state, "observed_state")
    _require_text(finding.desired_state, "desired_state")
    if finding.material:
        cfbe_prepass_ref = _require_text(cfbe_prepass_ref, "cfbe_prepass_ref")
    priority = finding_priority(finding)
    ranked = rank_routes(routes)
    route_by_id = {route.route_id: route for route in routes}
    eligible_ranked = [item for item in ranked if item[1] >= 0]
    callable_ranked = [item for item in eligible_ranked if route_by_id[item[0]].callable_now]
    selected_key = callable_ranked[0][0] if callable_ranked else (eligible_ranked[0][0] if eligible_ranked else None)
    selected = route_by_id[selected_key] if selected_key else None
    fingerprint = failure_fingerprint(
        finding,
        selected,
        source_epoch=source_epoch,
        authority_state=authority_state,
        failure_semantics=failure_semantics,
    )
    repeated = fingerprint in set(prior_failure_fingerprints)

    if not finding.material:
        repair_class = RepairClass.NOT_APPLICABLE
        state = TransactionState.NOT_APPLICABLE
        resume_trigger = None
    elif finding.prohibited:
        repair_class = RepairClass.REJECTED_WITH_EVIDENCE
        state = TransactionState.REJECTED_WITH_EVIDENCE
        resume_trigger = None
    elif finding.consequential_external_effect or finding.exact_provider_or_owner_trigger or finding.authority_gap > 0:
        repair_class = RepairClass.OWNER_OR_PROVIDER_TRIGGER_REQUIRED
        state = TransactionState.HELD_EXACT_GATE
        resume_trigger = "RECHECK_ON_EXACT_AUTHORITY_OR_PROVIDER_CAPABILITY_CHANGE"
    elif selected is None or not selected.callable_now:
        repair_class = RepairClass.WAITING_EXACT_CAPABILITY
        state = TransactionState.WAITING
        resume_trigger = "RECHECK_ON_CAPABILITY_SURFACE_OR_EXECUTOR_CHANGE"
    elif not (
        selected.reversible
        and selected.zero_or_included_cost
        and selected.within_a1_authority
        and selected.rollback_available
        and selected.independent_readback_available
    ):
        repair_class = RepairClass.OWNER_OR_PROVIDER_TRIGGER_REQUIRED
        state = TransactionState.HELD_EXACT_GATE
        resume_trigger = "RECHECK_ON_AUTHORITY_COST_ROLLBACK_OR_READBACK_CHANGE"
    elif repeated:
        repair_class = RepairClass.QUARANTINE_AND_REROUTE
        state = TransactionState.QUARANTINED
        resume_trigger = "RETRY_ONLY_AFTER_MATERIAL_ROUTE_SOURCE_AUTHORITY_OR_DEPENDENCY_CHANGE"
    elif selected.requires_canary:
        repair_class = RepairClass.AUTO_REPAIR_CANARY
        state = TransactionState.READY
        resume_trigger = None
    elif selected.requires_shared_state_fence:
        repair_class = RepairClass.AUTO_REPAIR_FENCED
        state = TransactionState.READY
        resume_trigger = None
    else:
        repair_class = RepairClass.AUTO_REPAIR_NOW
        state = TransactionState.READY
        resume_trigger = None

    preconditions = [
        "FRESH_SOURCE_EPOCH",
        "FRESH_TARGET_IDENTITY",
        "CURRENT_AUTHORITY_READBACK",
        "ROLLBACK_POINTER_PRESENT",
        "NO_REPEATED_UNCHANGED_FAILURE_ROUTE",
    ]
    if selected and selected.requires_shared_state_fence:
        preconditions.append("FDOF_FENCE_ACQUIRED_WITH_CURRENT_SOURCE")
    if selected and selected.requires_canary:
        preconditions.append("FAILURE_FIRST_CANARY_REQUIRED")

    proof_gates = (
        "FAILURE_FIRST_TEST",
        "SEMANTIC_TARGET_NATIVE_READBACK",
        "INDEPENDENT_ASSURANCE",
        "NO_REGRESSION",
        "ROLLBACK_VALID",
        "AUTHORITY_AND_COST_PRESERVED",
        "VALUE_POSITIVE_OR_SEPARATELY_JUSTIFIED_SAFETY_PROOF_GAIN",
    )
    transaction_id = f"ARC-{finding.finding_id}-{fingerprint[:12]}"
    unsigned = {
        "schema": SCHEMA,
        "version": VERSION,
        "transaction_id": transaction_id,
        "finding_id": finding.finding_id,
        "repair_class": repair_class.value,
        "state": state.value,
        "priority_score": priority,
        "selected_route_id": None if selected is None else selected.route_id,
        "route_rankings": ranked,
        "hypothesis": asdict(hypothesis or _default_hypothesis(finding)),
        "failure_fingerprint": fingerprint,
        "source_epoch": source_epoch,
        "authority_state": authority_state,
        "failure_semantics": failure_semantics,
        "repeated_unchanged_failure": repeated,
        "required_preconditions": preconditions,
        "proof_gates": proof_gates,
        "rollback_required": True,
        "resume_trigger": resume_trigger,
        "ledger_targets": (
            "KIOAS_FAILURE_BOOK",
            "KIOAS_LEARNING_LEDGER",
            "KIOAS_ROUTE_MEMORY",
            "KIOAS_EXPERIMENT_QUEUE",
            "CFBE_AUTO_IMPROVEMENT_QUEUE",
            "CFBE_RESOURCE_CAPABILITY_GATE",
            "CFBE_VALUE_REALIZATION_LEDGER",
            "FEDERATION_TURN_CAPTURE",
        ),
        "authority_ceiling": AUTHORITY_CEILING,
        "external_effect_authorized": False,
        "self_certification_allowed": False,
        "cfbe_prepass_ref": cfbe_prepass_ref,
        "benchmark_refs": CFBE_BENCHMARK_REFS,
    }
    transaction = RepairTransaction(
        transaction_id=transaction_id,
        finding_id=finding.finding_id,
        repair_class=repair_class,
        state=state,
        priority_score=priority,
        selected_route_id=None if selected is None else selected.route_id,
        route_rankings=ranked,
        hypothesis=hypothesis or _default_hypothesis(finding),
        failure_fingerprint=fingerprint,
        source_epoch=source_epoch,
        authority_state=authority_state,
        failure_semantics=failure_semantics,
        repeated_unchanged_failure=repeated,
        required_preconditions=tuple(preconditions),
        proof_gates=proof_gates,
        rollback_required=True,
        resume_trigger=resume_trigger,
        ledger_targets=tuple(unsigned["ledger_targets"]),
        cfbe_prepass_ref=cfbe_prepass_ref,
        benchmark_refs=CFBE_BENCHMARK_REFS,
        receipt_sha256="",
    )
    return _rerender_receipt(transaction)


def _rerender_receipt(transaction: RepairTransaction) -> RepairTransaction:
    payload = asdict(transaction)
    payload["receipt_sha256"] = ""
    return replace(transaction, receipt_sha256=_digest(payload))


def mark_applied(transaction: RepairTransaction, *, executor_id: str, execution_ref: str) -> RepairTransaction:
    """Mark a READY repair as executed but explicitly unverified."""
    if transaction.state != TransactionState.READY:
        raise ValueError("TRANSACTION_NOT_READY_FOR_APPLY")
    executor_id = _require_text(executor_id, "executor_id")
    execution_ref = _require_text(execution_ref, "execution_ref")
    return _rerender_receipt(
        replace(
            transaction,
            state=TransactionState.APPLIED_UNVERIFIED,
            executor_id=executor_id,
            execution_ref=execution_ref,
        )
    )


def verify_transaction(transaction: RepairTransaction, result: VerificationResult) -> RepairTransaction:
    """Independent proof result advances an applied repair; compiler cannot self-certify."""
    if transaction.state != TransactionState.APPLIED_UNVERIFIED:
        raise ValueError("TRANSACTION_NOT_APPLIED_UNVERIFIED")
    verifier_id = _require_text(result.verifier_id, "verifier_id")
    verification_ref = _require_text(result.verification_ref, "verification_ref")
    if transaction.executor_id and verifier_id == transaction.executor_id:
        raise ValueError("INDEPENDENT_VERIFIER_REQUIRED")
    verified = all(
        (
            result.semantic_readback,
            result.independent_assurance,
            result.regression_pass,
            result.rollback_valid,
            result.authority_preserved,
            result.cost_preserved,
            result.value_positive_or_justified,
        )
    )
    next_state = TransactionState.REPAIRED_VERIFIED if verified else TransactionState.APPLIED_UNVERIFIED
    return _rerender_receipt(
        replace(
            transaction,
            state=next_state,
            verifier_id=verifier_id,
            verification_ref=verification_ref,
        )
    )


def terminality_court(transactions: Sequence[RepairTransaction]) -> AuditTerminality:
    executable_open = sum(
        t.state in {TransactionState.COMPILED, TransactionState.READY, TransactionState.QUARANTINED}
        for t in transactions
    )
    applied_unverified = sum(t.state == TransactionState.APPLIED_UNVERIFIED for t in transactions)
    held = sum(t.state in {TransactionState.WAITING, TransactionState.HELD_EXACT_GATE} for t in transactions)
    repaired = sum(t.state == TransactionState.REPAIRED_VERIFIED for t in transactions)
    terminal_count = sum(t.state in TERMINAL_STATES for t in transactions)
    total = len(transactions)

    if executable_open:
        state = "AUDIT_OPEN_EXECUTABLE_REPAIRS"
    elif applied_unverified:
        state = "AUDIT_OPEN_UNVERIFIED_REPAIRS"
    elif held:
        state = "AUDIT_TERMINAL_WITH_RESUMABLE_EXACT_GATES"
    elif terminal_count == total:
        state = "AUDIT_VERIFIED_TERMINAL"
    else:
        state = "AUDIT_OPEN_INDETERMINATE"
    return AuditTerminality(
        state=state,
        executable_open=executable_open,
        applied_unverified=applied_unverified,
        held_exact_gate=held,
        repaired_verified=repaired,
        terminal_count=terminal_count,
        total_count=total,
    )




def compile_execution_packet(transaction: RepairTransaction) -> RepairExecutionPacket:
    """Compile a no-effect handoff packet for the existing Federation execution mesh."""
    if transaction.state != TransactionState.READY:
        raise ValueError("TRANSACTION_NOT_READY_FOR_EXECUTION_PACKET")
    if transaction.repair_class not in {
        RepairClass.AUTO_REPAIR_NOW,
        RepairClass.AUTO_REPAIR_FENCED,
        RepairClass.AUTO_REPAIR_CANARY,
    }:
        raise ValueError("REPAIR_CLASS_NOT_EXECUTABLE")
    route_id = _require_text(transaction.selected_route_id or "", "selected_route_id")
    unsigned = {
        "schema": "KIOAS-ARC-EXECUTION-PACKET-V1",
        "transaction_id": transaction.transaction_id,
        "finding_id": transaction.finding_id,
        "selected_route_id": route_id,
        "repair_class": transaction.repair_class.value,
        "source_epoch": transaction.source_epoch,
        "authority_state": transaction.authority_state,
        "failure_fingerprint": transaction.failure_fingerprint,
        "idempotency_key": transaction.transaction_id,
        "required_preconditions": transaction.required_preconditions,
        "proof_gates": transaction.proof_gates,
        "rollback_required": transaction.rollback_required,
        "executor_contract": "FEDERATION_EXECUTION_MESH",
        "authority_ceiling": transaction.authority_ceiling,
        "external_effect_authorized": False,
        "provider_effect_authorized": False,
        "self_certification_allowed": False,
    }
    return RepairExecutionPacket(**unsigned, receipt_sha256=_digest(unsigned))


def compile_resume_packet(transaction: RepairTransaction) -> ResumePacket:
    """Compile a GAS-GNS3-only wake packet for waiting exact-capability/gate states."""
    if transaction.state not in {TransactionState.WAITING, TransactionState.HELD_EXACT_GATE}:
        raise ValueError("TRANSACTION_NOT_RESUMABLE_WAIT_STATE")
    trigger = _require_text(transaction.resume_trigger or "", "resume_trigger")
    unsigned = {
        "schema": "KIOAS-ARC-GNS3-RESUME-PACKET-V1",
        "transaction_id": transaction.transaction_id,
        "finding_id": transaction.finding_id,
        "transaction_state": transaction.state.value,
        "repair_class": transaction.repair_class.value,
        "source_epoch": transaction.source_epoch,
        "authority_state": transaction.authority_state,
        "resume_trigger": trigger,
        "scheduler_surface": "GOOGLE_APPS_SCRIPT_GNS3",
        "chatgpt_scheduler_allowed": False,
        "affected_controller_only": True,
        "external_effect_authorized": False,
    }
    return ResumePacket(**unsigned, receipt_sha256=_digest(unsigned))


def compile_candidate_artifact_identity(
    *,
    logical_name: str,
    version: str,
    payload: bytes,
    source_epoch: str,
) -> CandidateArtifactIdentity:
    """Create a content-addressed identity; competing candidates never share mutable bytes."""
    logical_name = _require_text(logical_name, "logical_name")
    version = _require_text(version, "version")
    source_epoch = _require_text(source_epoch, "source_epoch")
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise ValueError("CANDIDATE_PAYLOAD_REQUIRED")
    digest = sha256(bytes(payload)).hexdigest()
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in logical_name).strip("-")
    if not safe_name:
        raise ValueError("LOGICAL_NAME_INVALID")
    immutable_file_name = f"{safe_name}_{version}_{digest[:16]}.zip"
    unsigned = {
        "schema": "KIOAS-ARC-CONTENT-ADDRESSED-CANDIDATE-V1",
        "logical_name": logical_name,
        "version": version,
        "sha256": digest,
        "size_bytes": len(payload),
        "immutable_file_name": immutable_file_name,
        "source_epoch": source_epoch,
        "write_mode": "CREATE_IMMUTABLE_CANDIDATE",
        "canonical_pointer_mutation": "COMPARE_AND_SET_ONLY",
        "delete_superseded": False,
    }
    return CandidateArtifactIdentity(**unsigned, receipt_sha256=_digest(unsigned))


def decide_canonical_pointer_promotion(
    *,
    observed_sha256: str,
    expected_observed_sha256: str,
    candidate_sha256: str,
) -> CanonicalPointerDecision:
    """CAS gate for the canonical pointer; stale writers fail without mutating candidate history."""
    observed = _require_text(observed_sha256, "observed_sha256").lower()
    expected = _require_text(expected_observed_sha256, "expected_observed_sha256").lower()
    candidate = _require_text(candidate_sha256, "candidate_sha256").lower()
    for value, label in ((observed, "OBSERVED_SHA256"), (expected, "EXPECTED_OBSERVED_SHA256"), (candidate, "CANDIDATE_SHA256")):
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError(f"{label}_INVALID")
    if observed != expected:
        state = "HOLD_CONCURRENT_DRIFT"
        allowed = False
    elif observed == candidate:
        state = "ALREADY_CURRENT"
        allowed = False
    else:
        state = "PROMOTE_POINTER_ONLY"
        allowed = True
    unsigned = {
        "state": state,
        "observed_sha256": observed,
        "expected_observed_sha256": expected,
        "candidate_sha256": candidate,
        "mutation_allowed": allowed,
        "requires_fresh_readback": True,
        "delete_superseded": False,
    }
    return CanonicalPointerDecision(**unsigned, receipt_sha256=_digest(unsigned))


def transaction_to_mapping(transaction: RepairTransaction) -> dict[str, Any]:
    """Serialize a transaction for durable checkpointing without changing semantics."""
    payload = asdict(transaction)
    payload["repair_class"] = transaction.repair_class.value
    payload["state"] = transaction.state.value
    payload["route_rankings"] = [list(item) for item in transaction.route_rankings]
    payload["required_preconditions"] = list(transaction.required_preconditions)
    payload["proof_gates"] = list(transaction.proof_gates)
    payload["ledger_targets"] = list(transaction.ledger_targets)
    payload["benchmark_refs"] = list(transaction.benchmark_refs)
    return payload


def transaction_from_mapping(payload: Mapping[str, Any], *, verify_receipt: bool = True) -> RepairTransaction:
    """Restore a checkpointed transaction and fail closed on tampering."""
    raw = dict(payload)
    hypothesis_raw = dict(raw.get("hypothesis") or {})
    transaction = RepairTransaction(
        transaction_id=_require_text(raw.get("transaction_id", ""), "transaction_id"),
        finding_id=_require_text(raw.get("finding_id", ""), "finding_id"),
        repair_class=RepairClass(raw.get("repair_class")),
        state=TransactionState(raw.get("state")),
        priority_score=float(raw.get("priority_score", 0)),
        selected_route_id=raw.get("selected_route_id"),
        route_rankings=tuple((str(item[0]), float(item[1])) for item in raw.get("route_rankings", ())),
        hypothesis=RepairHypothesis(**hypothesis_raw),
        failure_fingerprint=_require_text(raw.get("failure_fingerprint", ""), "failure_fingerprint"),
        source_epoch=_require_text(raw.get("source_epoch", ""), "source_epoch"),
        authority_state=_require_text(raw.get("authority_state", ""), "authority_state"),
        failure_semantics=_require_text(raw.get("failure_semantics", ""), "failure_semantics"),
        repeated_unchanged_failure=bool(raw.get("repeated_unchanged_failure", False)),
        required_preconditions=tuple(str(v) for v in raw.get("required_preconditions", ())),
        proof_gates=tuple(str(v) for v in raw.get("proof_gates", ())),
        rollback_required=bool(raw.get("rollback_required", True)),
        resume_trigger=raw.get("resume_trigger"),
        ledger_targets=tuple(str(v) for v in raw.get("ledger_targets", ())),
        authority_ceiling=str(raw.get("authority_ceiling", AUTHORITY_CEILING)),
        external_effect_authorized=bool(raw.get("external_effect_authorized", False)),
        self_certification_allowed=bool(raw.get("self_certification_allowed", False)),
        executor_id=raw.get("executor_id"),
        execution_ref=raw.get("execution_ref"),
        verifier_id=raw.get("verifier_id"),
        verification_ref=raw.get("verification_ref"),
        cfbe_prepass_ref=str(raw.get("cfbe_prepass_ref", "")),
        benchmark_refs=tuple(str(v) for v in raw.get("benchmark_refs", CFBE_BENCHMARK_REFS)),
        receipt_sha256=str(raw.get("receipt_sha256", "")),
    )
    if verify_receipt and not validate_transaction_receipt(transaction):
        raise ValueError("TRANSACTION_RECEIPT_INVALID")
    return transaction


def validate_transaction_receipt(transaction: RepairTransaction) -> bool:
    payload = asdict(transaction)
    claimed = str(payload.pop("receipt_sha256", ""))
    payload["receipt_sha256"] = ""
    return bool(claimed) and claimed == _digest(payload)


def resume_disposition(
    transaction: RepairTransaction,
    *,
    current_source_epoch: str,
    current_authority_state: str,
) -> str:
    """Decide the safest crash/restart action without re-executing uncertain effects."""
    current_source_epoch = _require_text(current_source_epoch, "current_source_epoch")
    current_authority_state = _require_text(current_authority_state, "current_authority_state")
    if not validate_transaction_receipt(transaction):
        return "QUARANTINE_TAMPERED_CHECKPOINT"
    if transaction.state == TransactionState.APPLIED_UNVERIFIED:
        return "READBACK_BEFORE_ANY_REEXECUTION"
    if current_source_epoch != transaction.source_epoch:
        return "RECOMPILE_JIT_SOURCE_DRIFT"
    if current_authority_state != transaction.authority_state:
        return "RECOMPILE_AUTHORITY_DRIFT"
    if transaction.state == TransactionState.WAITING:
        return "RECHECK_RESUME_TRIGGER"
    if transaction.state == TransactionState.QUARANTINED:
        return "MATERIAL_ROUTE_CHANGE_REQUIRED"
    if transaction.state == TransactionState.READY:
        return "RESUME_READY_TRANSACTION"
    if transaction.state in TERMINAL_STATES:
        return "NO_ACTION_TERMINAL"
    return "HOLD_UNKNOWN_STATE"

def compile_audit(
    findings: Sequence[AuditFinding],
    routes_by_finding: Mapping[str, Sequence[RepairRoute]],
    *,
    source_epoch: str,
    authority_state: str,
    failure_semantics_by_finding: Mapping[str, str],
    prior_failure_fingerprints: Iterable[str] = (),
    cfbe_prepass_ref: str = "",
) -> tuple[RepairTransaction, ...]:
    transactions = []
    for finding in findings:
        transactions.append(
            compile_finding(
                finding,
                tuple(routes_by_finding.get(finding.finding_id, ())),
                source_epoch=source_epoch,
                authority_state=authority_state,
                failure_semantics=failure_semantics_by_finding.get(finding.finding_id, "UNSPECIFIED"),
                prior_failure_fingerprints=prior_failure_fingerprints,
                cfbe_prepass_ref=cfbe_prepass_ref,
            )
        )
    return tuple(sorted(transactions, key=lambda t: (-t.priority_score, t.finding_id)))


__all__ = [
    "AUTHORITY_CEILING",
    "CFBE_BENCHMARK_REFS",
    "SCHEMA",
    "VERSION",
    "AuditFinding",
    "AuditTerminality",
    "RepairClass",
    "RepairHypothesis",
    "RepairRoute",
    "RepairTransaction",
    "RepairExecutionPacket",
    "ResumePacket",
    "CandidateArtifactIdentity",
    "CanonicalPointerDecision",
    "TransactionState",
    "VerificationResult",
    "compile_audit",
    "compile_finding",
    "compile_execution_packet",
    "compile_resume_packet",
    "compile_candidate_artifact_identity",
    "decide_canonical_pointer_promotion",
    "failure_fingerprint",
    "finding_priority",
    "mark_applied",
    "rank_routes",
    "route_score",
    "terminality_court",
    "transaction_from_mapping",
    "transaction_to_mapping",
    "validate_transaction_receipt",
    "resume_disposition",
    "verify_transaction",
]
