"""N-OMEGA ↔ CFBE Chat Hyperperformance v2 runtime guard.

This module makes the v2 execution controls composable as one pre-output/pre-action
court. It does not execute providers or grant authority. A host can call this court
before emitting a continuation/report or dispatching the next already-authorised
operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Sequence

from federation.cfbe_chat_hyperperformance_v2 import (
    ActionKind,
    DirectiveDuplicateGuard,
    ExecutionArbiter,
    ExecutionState,
    FailureEvolutionEngine,
    FailureObservation,
    ProgressSnapshot,
    monotonic_progress,
)

SCHEMA = "N-OMEGA-CFBE-RUNTIME-GUARD-V2"
VERSION = "2.0.0"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeGuardRequest:
    mission_id: str
    proposed_action: ActionKind
    execution_state: ExecutionState
    previous_directive: str = ""
    proposed_directive: str = ""
    previous_progress: ProgressSnapshot = ProgressSnapshot()
    current_progress: ProgressSnapshot = ProgressSnapshot()
    current_failure: FailureObservation | None = None
    failure_history: tuple[FailureObservation, ...] = ()
    candidate_recovery_routes: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.mission_id.strip():
            raise ValueError("MISSION_ID_REQUIRED")
        if self.execution_state.mission_id != self.mission_id:
            raise ValueError("EXECUTION_STATE_MISSION_MISMATCH")
        if bool(self.previous_directive.strip()) != bool(self.proposed_directive.strip()):
            raise ValueError("DIRECTIVE_PAIR_REQUIRED")


@dataclass(frozen=True, slots=True)
class RuntimeGuardReceipt:
    mission_id: str
    state: str
    required_action: str
    selected_recovery_route: str
    duplicate_directive: bool
    monotonic_progress_observed: bool
    reasons: tuple[str, ...]
    receipt_digest: str

    @property
    def admitted(self) -> bool:
        return self.state == "N_OMEGA_CFBE_RUNTIME_ADMITTED"


class NOmegaCFBERuntimeGuardV2:
    """Fail closed on report-before-execute, duplicate n, or non-evolving recovery."""

    def __init__(self, *, directive_similarity_threshold: float = 0.82) -> None:
        self.arbiter = ExecutionArbiter()
        self.duplicate_guard = DirectiveDuplicateGuard(directive_similarity_threshold)
        self.failure_engine = FailureEvolutionEngine()

    def evaluate(self, request: RuntimeGuardRequest) -> RuntimeGuardReceipt:
        request.validate()
        reasons: list[str] = []
        selected_recovery_route = ""

        arbitration = self.arbiter.decide(request.execution_state, request.proposed_action)
        if not arbitration.allowed:
            reasons.extend(arbitration.reasons)

        progressed = monotonic_progress(request.previous_progress, request.current_progress)
        new_execution_evidence = bool(request.execution_state.new_evidence_refs) or progressed

        duplicate = False
        if request.previous_directive:
            comparison = self.duplicate_guard.compare(
                request.previous_directive,
                request.proposed_directive,
                new_execution_evidence=new_execution_evidence,
            )
            duplicate = comparison.duplicate
            if not comparison.allowed:
                reasons.append(comparison.reason)

        if request.current_failure is not None:
            recovery = self.failure_engine.decide(
                request.current_failure,
                request.failure_history,
                request.candidate_recovery_routes,
            )
            selected_recovery_route = recovery.selected_route
            if recovery.action in {"SWITCH_ROUTE", "ALGORITHM_FOUNDRY", "ARCHITECTURE_REMEDIATION"}:
                reasons.extend(recovery.reasons)
                reasons.append("RECOVERY_ACTION:" + recovery.action)

        if (
            not progressed
            and request.proposed_action in {ActionKind.REPORT, ActionKind.CHECKPOINT}
            and not request.execution_state.owner_gate_required
            and not request.execution_state.terminal_complete
        ):
            reasons.append("NO_MONOTONIC_PROGRESS_FOR_NARRATIVE_OUTPUT")

        required_action = arbitration.required_action
        if selected_recovery_route:
            required_action = "RECOVERY_ROUTE:" + selected_recovery_route
        elif "DUPLICATE_DIRECTIVE_WITHOUT_NEW_EVIDENCE" in reasons:
            required_action = "EXECUTE_OR_EVOLVE_BEFORE_NEXT_DIRECTIVE"
        elif "NO_MONOTONIC_PROGRESS_FOR_NARRATIVE_OUTPUT" in reasons and arbitration.allowed:
            required_action = "EXECUTE_OR_ALGORITHM_FOUNDRY"

        unique_reasons = tuple(dict.fromkeys(reasons))
        state = "N_OMEGA_CFBE_RUNTIME_ADMITTED" if not unique_reasons else "N_OMEGA_CFBE_RUNTIME_HELD"
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": request.mission_id,
            "state": state,
            "required_action": required_action,
            "selected_recovery_route": selected_recovery_route,
            "duplicate_directive": duplicate,
            "monotonic_progress_observed": progressed,
            "reasons": unique_reasons,
        }
        return RuntimeGuardReceipt(
            mission_id=request.mission_id,
            state=state,
            required_action=required_action,
            selected_recovery_route=selected_recovery_route,
            duplicate_directive=duplicate,
            monotonic_progress_observed=progressed,
            reasons=unique_reasons,
            receipt_digest=_digest(material),
        )


__all__ = [
    "NOmegaCFBERuntimeGuardV2",
    "RuntimeGuardReceipt",
    "RuntimeGuardRequest",
    "SCHEMA",
    "VERSION",
]
