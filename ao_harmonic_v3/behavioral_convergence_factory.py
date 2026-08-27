from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from formation_omega.autonomic_fabric import (
    ActionCandidate,
    AuthorityCeiling,
    ProofDirectedScheduler,
    ScheduledAction,
)

from .failure_win_v2 import FailureEventType


class CandidateDisposition(str, Enum):
    """Pre-execution classification for receiver behavioral convergence work."""

    EXECUTABLE_RECOVERY = "EXECUTABLE_RECOVERY"
    HOLD_AUTHORITY = "HOLD_AUTHORITY"
    HOLD_ROLLBACK = "HOLD_ROLLBACK"
    HOLD_READBACK = "HOLD_READBACK"
    HOLD_SURFACE_BINDING = "HOLD_SURFACE_BINDING"
    REJECT_ADMISSION_ONLY = "REJECT_ADMISSION_ONLY"
    REJECT_TEST_HARNESS_ONLY = "REJECT_TEST_HARNESS_ONLY"
    REJECT_SYNTHETIC_ONLY = "REJECT_SYNTHETIC_ONLY"
    REJECT_SUCCESS_ONLY = "REJECT_SUCCESS_ONLY"
    REJECT_STALE = "REJECT_STALE"
    REJECT_UNPRESERVED_FAILURE = "REJECT_UNPRESERVED_FAILURE"
    REJECT_SURFACE_MISMATCH = "REJECT_SURFACE_MISMATCH"
    REJECT_NON_MATERIAL = "REJECT_NON_MATERIAL"


@dataclass(frozen=True)
class BehavioralCandidate:
    """One preserved receiver event plus a proposed recovery/investigation lane.

    The semantic surface is the behavior being proved, not the transport route.
    A materially different route may be used while the semantic surface remains
    identical. This class never grants provider authority or behavioral maturity.
    """

    receiver_id: str
    event_id: str
    event_type: FailureEventType
    semantic_surface: str
    recovery_semantic_surface: str
    objective: str
    failure_preserved: bool = True
    current: bool = True
    proof_fresh: bool = True
    material: bool = True
    success_only: bool = False
    admission_only: bool = False
    test_harness_only: bool = False
    synthetic_only: bool = False
    authority_ready: bool = True
    owner_authority_required: bool = False
    external_effect_required: bool = False
    external_effect_authorized: bool = False
    rollback_available: bool = True
    independent_readback_available: bool = True
    closure_leverage: float = 0.5
    information_gain: float = 0.5
    success_probability: float = 0.5
    reversibility: float = 0.5
    cost: float = 0.0
    risk: float = 0.0
    latency: float = 0.0
    owner_burden: float = 0.0
    unlock_count: int = 0
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.receiver_id.strip():
            raise ValueError("receiver_id is required")
        if not self.event_id.strip():
            raise ValueError("event_id is required")
        if not self.objective.strip():
            raise ValueError("objective is required")
        if min(self.cost, self.risk, self.latency, self.owner_burden) < 0:
            raise ValueError("cost/risk/latency/owner_burden must be non-negative")
        if self.unlock_count < 0:
            raise ValueError("unlock_count must be non-negative")


@dataclass(frozen=True)
class CandidateAssessment:
    receiver_id: str
    event_id: str
    disposition: CandidateDisposition
    reason: str
    semantic_surface: str
    recovery_semantic_surface: str

    @property
    def executable(self) -> bool:
        return self.disposition is CandidateDisposition.EXECUTABLE_RECOVERY


@dataclass(frozen=True)
class BehavioralConvergencePlan:
    assessments: tuple[CandidateAssessment, ...]
    selected_wave: tuple[ScheduledAction, ...]

    @property
    def selected_event_ids(self) -> tuple[str, ...]:
        return tuple(item.action.action_id for item in self.selected_wave)

    @property
    def selected_receiver_ids(self) -> tuple[str, ...]:
        return tuple(item.action.shared_state_key or "" for item in self.selected_wave)


class BehavioralConvergenceFactory:
    """Fail-closed receiver-failure triage and proof-directed work selection.

    This prevents convergence work from starting on evidence that cannot earn
    receiver behavioral credit. Failure-Win v2 remains the proof/promotion gate.
    """

    def __init__(self, *, max_parallel: int = 4) -> None:
        if max_parallel < 1:
            raise ValueError("max_parallel must be at least one")
        self.max_parallel = max_parallel
        self.scheduler = ProofDirectedScheduler(
            authority_ceiling=AuthorityCeiling.A1_INTERNAL,
            allow_external_effects=False,
        )

    @staticmethod
    def _normalize_surface(value: str) -> str:
        return " ".join(value.casefold().split())

    @classmethod
    def classify(cls, candidate: BehavioralCandidate) -> CandidateAssessment:
        surface = cls._normalize_surface(candidate.semantic_surface)
        recovery_surface = cls._normalize_surface(candidate.recovery_semantic_surface)

        def assessment(disposition: CandidateDisposition, reason: str) -> CandidateAssessment:
            return CandidateAssessment(
                receiver_id=candidate.receiver_id,
                event_id=candidate.event_id,
                disposition=disposition,
                reason=reason,
                semantic_surface=surface,
                recovery_semantic_surface=recovery_surface,
            )

        if not candidate.current or not candidate.proof_fresh:
            return assessment(CandidateDisposition.REJECT_STALE, "EVENT_OR_PROOF_NOT_CURRENT")
        if not candidate.material:
            return assessment(CandidateDisposition.REJECT_NON_MATERIAL, "EVENT_NOT_MATERIAL")
        if not candidate.failure_preserved:
            return assessment(CandidateDisposition.REJECT_UNPRESERVED_FAILURE, "FAILURE_FACT_NOT_PRESERVED")
        if candidate.success_only:
            return assessment(CandidateDisposition.REJECT_SUCCESS_ONLY, "NO_FAILURE_ANTECEDENT")
        if candidate.admission_only:
            return assessment(CandidateDisposition.REJECT_ADMISSION_ONLY, "ADMISSION_OR_SETUP_FAILURE_NOT_RECEIVER_BEHAVIOR")
        if candidate.test_harness_only:
            return assessment(CandidateDisposition.REJECT_TEST_HARNESS_ONLY, "TEST_HARNESS_FAILURE_NOT_RECEIVER_BEHAVIOR")
        if candidate.synthetic_only:
            return assessment(CandidateDisposition.REJECT_SYNTHETIC_ONLY, "SYNTHETIC_EVENT_CANNOT_EARN_REAL_BEHAVIOR_CREDIT")
        if not surface or not recovery_surface:
            return assessment(CandidateDisposition.HOLD_SURFACE_BINDING, "SEMANTIC_SURFACE_BINDING_INCOMPLETE")
        if surface != recovery_surface:
            return assessment(CandidateDisposition.REJECT_SURFACE_MISMATCH, "RECOVERY_TARGET_DIFFERS_FROM_FAILED_SEMANTIC_SURFACE")
        if candidate.owner_authority_required and not candidate.authority_ready:
            return assessment(CandidateDisposition.HOLD_AUTHORITY, "OWNER_OR_PROVIDER_AUTHORITY_REQUIRED")
        if not candidate.authority_ready:
            return assessment(CandidateDisposition.HOLD_AUTHORITY, "CURRENT_AUTHORITY_NOT_PROVEN")
        if candidate.external_effect_required and not candidate.external_effect_authorized:
            return assessment(CandidateDisposition.HOLD_AUTHORITY, "EXTERNAL_EFFECT_NOT_AUTHORIZED")
        if not candidate.rollback_available:
            return assessment(CandidateDisposition.HOLD_ROLLBACK, "ROLLBACK_NOT_AVAILABLE")
        if not candidate.independent_readback_available:
            return assessment(CandidateDisposition.HOLD_READBACK, "INDEPENDENT_READBACK_NOT_AVAILABLE")
        return assessment(CandidateDisposition.EXECUTABLE_RECOVERY, "REAL_EVENT_WITH_EXECUTABLE_PROOF_LANE")

    @staticmethod
    def _action(candidate: BehavioralCandidate) -> ActionCandidate:
        return ActionCandidate(
            action_id=candidate.event_id,
            objective=candidate.objective,
            closure_leverage=candidate.closure_leverage,
            information_gain=candidate.information_gain,
            success_probability=candidate.success_probability,
            reversibility=candidate.reversibility,
            cost=candidate.cost + candidate.owner_burden,
            risk=candidate.risk,
            latency=candidate.latency,
            unlock_count=candidate.unlock_count,
            shared_state_key=candidate.receiver_id,
            authority_ceiling=AuthorityCeiling.A1_INTERNAL,
            external_effect=False,
            required_capabilities=("failure-win-v2", "independent-readback", "rollback"),
            evidence_refs=candidate.evidence_refs,
        )

    def plan(self, candidates: Iterable[BehavioralCandidate]) -> BehavioralConvergencePlan:
        materialized = tuple(candidates)
        assessments = tuple(self.classify(item) for item in materialized)
        executable_ids = {item.event_id for item in assessments if item.executable}
        actions = tuple(self._action(item) for item in materialized if item.event_id in executable_ids)
        selected = self.scheduler.ready_wave(actions, max_parallel=self.max_parallel)
        return BehavioralConvergencePlan(assessments=assessments, selected_wave=selected)
