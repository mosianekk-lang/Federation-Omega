#!/usr/bin/env python3
"""Federation Fully Established Gold Standard.

This module is provider-neutral. It evaluates whether a connection,
integration, automation, deployment, restoration, migration, or operational
capability has reached the Federation's terminal gold standard.

Intermediate states remain valid work-in-progress states. They may not be
promoted to terminal completion claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


RULE_ID = "FED-RULE-FULLY-ESTABLISHED-GOLD-STANDARD-V1"


class GateResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EstablishmentStage(str, Enum):
    DISCOVERED = "DISCOVERED"
    CONFIGURED = "CONFIGURED"
    REACHABLE = "REACHABLE"
    AUTHENTICATED = "AUTHENTICATED"
    AUTHORIZED = "AUTHORIZED"
    SEMANTICALLY_VERIFIED = "SEMANTICALLY_VERIFIED"
    BIDIRECTIONAL = "BIDIRECTIONAL"
    OPERATIONAL = "OPERATIONAL"
    RESILIENT = "RESILIENT"
    FULLY_ESTABLISHED = "FULLY_ESTABLISHED"


# Ordered stage gates. A stage is attained only when all gates in that stage
# and every preceding stage are satisfied.
STAGE_GATES: tuple[tuple[EstablishmentStage, tuple[str, ...]], ...] = (
    (
        EstablishmentStage.DISCOVERED,
        ("target_discovered", "exact_target_identity"),
    ),
    (
        EstablishmentStage.CONFIGURED,
        ("configuration_bound", "authority_scope_declared"),
    ),
    (
        EstablishmentStage.REACHABLE,
        ("forward_transport",),
    ),
    (
        EstablishmentStage.AUTHENTICATED,
        ("intended_identity_authenticated",),
    ),
    (
        EstablishmentStage.AUTHORIZED,
        ("action_specific_authorization",),
    ),
    (
        EstablishmentStage.SEMANTICALLY_VERIFIED,
        ("forward_semantic_readback", "fresh_readback"),
    ),
    (
        EstablishmentStage.BIDIRECTIONAL,
        ("reverse_transport", "reverse_semantic_readback"),
    ),
    (
        EstablishmentStage.OPERATIONAL,
        (
            "monitoring_active",
            "freshness_lease_active",
            "idempotency_proven",
            "duplicate_effect_suppression_proven",
        ),
    ),
    (
        EstablishmentStage.RESILIENT,
        (
            "retry_dlq_replay_proven",
            "failure_isolation_proven",
            "missed_run_recovery_proven",
            "rollback_proven",
        ),
    ),
    (
        EstablishmentStage.FULLY_ESTABLISHED,
        (
            "sustained_soak_passed",
            "zero_critical_regressions",
            "jarvis_assurance_passed",
            "cfbe_benchmark_passed",
            "sentinel_observation_current",
            "canonical_state_synchronized",
            "owner_effect_gate_satisfied",
        ),
    ),
)

REQUIRED_GATES: tuple[str, ...] = tuple(
    gate for _, gates in STAGE_GATES for gate in gates
)

TERMINAL_CLAIMS: frozenset[str] = frozenset(
    {
        "ACTIVE",
        "CONNECTED",
        "CUTOVER_COMPLETE",
        "DEPLOYED",
        "DONE",
        "COMPLETE",
        "COMPLETED",
        "ESTABLISHED",
        "FULLY_OPERATIONAL",
        "MIGRATION_COMPLETE",
        "PRODUCTION_READY",
        "RESTORED",
        "SERVING",
        "CLOSED",
    }
)


class NotFullyEstablishedError(RuntimeError):
    """Raised when a terminal claim is attempted below the gold standard."""


@dataclass(frozen=True)
class EstablishmentRecord:
    work_id: str
    scope: str
    gate_results: Mapping[str, GateResult | str]
    proof_refs: tuple[str, ...] = ()
    not_applicable_justifications: Mapping[str, str] | None = None
    measured_at: str = ""

    def normalized_results(self) -> dict[str, GateResult]:
        normalized: dict[str, GateResult] = {}
        for gate in REQUIRED_GATES:
            raw = self.gate_results.get(gate, GateResult.UNKNOWN)
            normalized[gate] = raw if isinstance(raw, GateResult) else GateResult(str(raw))
        return normalized


@dataclass(frozen=True)
class EstablishmentDecision:
    rule_id: str
    work_id: str
    scope: str
    stage: EstablishmentStage
    fully_established: bool
    terminal_claim_allowed: bool
    missing_or_failed_gates: tuple[str, ...]
    invalid_not_applicable_gates: tuple[str, ...]
    proof_refs: tuple[str, ...]
    measured_at: str
    status: str


def _gate_satisfied(
    gate: str,
    result: GateResult,
    not_applicable_justifications: Mapping[str, str],
) -> tuple[bool, bool]:
    """Return (satisfied, invalid_not_applicable)."""
    if result is GateResult.PASS:
        return True, False
    if result is GateResult.NOT_APPLICABLE:
        justification = str(not_applicable_justifications.get(gate, "")).strip()
        return bool(justification), not bool(justification)
    return False, False


def evaluate_establishment(record: EstablishmentRecord) -> EstablishmentDecision:
    results = record.normalized_results()
    na = dict(record.not_applicable_justifications or {})
    current_stage = EstablishmentStage.DISCOVERED
    any_stage_passed = False
    missing: list[str] = []
    invalid_na: list[str] = []
    progression_open = True

    for stage, gates in STAGE_GATES:
        stage_ok = True
        for gate in gates:
            satisfied, invalid = _gate_satisfied(gate, results[gate], na)
            if invalid:
                invalid_na.append(gate)
            if not satisfied:
                stage_ok = False
                missing.append(gate)
        if progression_open and stage_ok:
            current_stage = stage
            any_stage_passed = True
        else:
            progression_open = False

    fully = (
        any_stage_passed
        and current_stage is EstablishmentStage.FULLY_ESTABLISHED
        and not missing
        and not invalid_na
        and bool(record.proof_refs)
        and bool(str(record.measured_at).strip())
    )

    if not any_stage_passed:
        current_stage = EstablishmentStage.DISCOVERED

    return EstablishmentDecision(
        rule_id=RULE_ID,
        work_id=record.work_id,
        scope=record.scope,
        stage=current_stage,
        fully_established=fully,
        terminal_claim_allowed=fully,
        missing_or_failed_gates=tuple(dict.fromkeys(missing)),
        invalid_not_applicable_gates=tuple(dict.fromkeys(invalid_na)),
        proof_refs=tuple(record.proof_refs),
        measured_at=record.measured_at,
        status="FULLY_ESTABLISHED" if fully else "IN_PROGRESS_NOT_TERMINALLY_ACCEPTABLE",
    )


def terminal_claim_allowed(
    record: EstablishmentRecord,
    claim: str,
) -> bool:
    normalized_claim = str(claim).strip().upper()
    if normalized_claim not in TERMINAL_CLAIMS:
        return True
    return evaluate_establishment(record).fully_established


def assert_terminal_claim(
    record: EstablishmentRecord,
    claim: str,
) -> EstablishmentDecision:
    decision = evaluate_establishment(record)
    normalized_claim = str(claim).strip().upper()
    if normalized_claim in TERMINAL_CLAIMS and not decision.fully_established:
        missing = ", ".join(decision.missing_or_failed_gates) or "proof/freshness"
        raise NotFullyEstablishedError(
            f"{RULE_ID}: terminal claim {normalized_claim!r} rejected for "
            f"{record.work_id}; current stage={decision.stage.value}; "
            f"missing={missing}"
        )
    return decision


def completion_status(record: EstablishmentRecord) -> str:
    """Return the only permitted unqualified terminal status."""
    decision = evaluate_establishment(record)
    return (
        "FULLY_ESTABLISHED"
        if decision.fully_established
        else "IN_PROGRESS_NOT_TERMINALLY_ACCEPTABLE"
    )


def all_pass_record(
    *,
    work_id: str = "TEST-WORK",
    scope: str = "TEST",
    proof_refs: Sequence[str] = ("proof:test",),
    measured_at: str = "2026-08-26T00:00:00+02:00",
) -> EstablishmentRecord:
    """Deterministic helper for tests and bounded canaries."""
    return EstablishmentRecord(
        work_id=work_id,
        scope=scope,
        gate_results={gate: GateResult.PASS for gate in REQUIRED_GATES},
        proof_refs=tuple(proof_refs),
        measured_at=measured_at,
    )
