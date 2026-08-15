from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


class TaskCompletionState(str, Enum):
    PENDING = "PENDING"
    OWNER_ASSERTED_COMPLETED = "OWNER_ASSERTED_COMPLETED"
    PROVIDER_VERIFIED_COMPLETED = "PROVIDER_VERIFIED_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WitnessMode(str, Enum):
    TOOL_RECEIPT = "TOOL_RECEIPT"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    APP_CALLBACK = "APP_CALLBACK"
    API_WEBHOOK = "API_WEBHOOK"
    USER_ASSERTION = "USER_ASSERTION"
    UI_OPAQUE = "UI_OPAQUE"


class ContinuationClass(str, Enum):
    SAFE_INTERNAL = "SAFE_INTERNAL"
    CONSEQUENTAL_EXTERNAL = "CONSEQUENTIAL_EXTERNAL"


@dataclass(frozen=True)
class CompletionObservation:
    witness_mode: WitnessMode
    success: bool
    correlation_ref: str = ""
    evidence_ref: str = ""
    provider: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def observation_id(self) -> str:
        material = "|".join(
            (
                self.witness_mode.value,
                str(self.success),
                self.correlation_ref,
                self.evidence_ref,
                self.provider,
                repr(sorted(self.payload.items())),
            )
        )
        return f"obs_{sha256(material.encode('utf-8')).hexdigest()[:20]}"


@dataclass(frozen=True)
class PendingUserTask:
    task_id: str
    task_type: str
    expected_effect: str
    continuation_action: str
    witness_modes: Tuple[WitnessMode, ...]
    continuation_class: ContinuationClass = ContinuationClass.SAFE_INTERNAL
    correlation_ref: str = ""
    provider: str = ""
    allow_owner_assertion_for_safe_continuation: bool = True
    require_provider_verification_for_terminal_claim: bool = True
    notes: str = ""


@dataclass(frozen=True)
class CompletionDecision:
    task_id: str
    state: TaskCompletionState
    evidence_ref: str
    may_continue: bool
    may_make_terminal_provider_claim: bool
    continuation_action: str
    reason: str
    observation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class CompletionWitnessEngine:
    """Proof-aware reconciliation for user-completed UI / provider tasks.

    The engine lets ChatBridge/ChatGov treat supported provider receipts, callbacks,
    webhooks and readbacks as first-class completion evidence. Opaque platform UI
    clicks are never silently upgraded to provider-verified completion.

    A user assertion such as "done" can still unlock safe internal continuation when
    policy allows, while terminal provider claims stay blocked until independent
    provider evidence exists.
    """

    def reconcile(
        self,
        task: PendingUserTask,
        observations: Iterable[CompletionObservation],
    ) -> CompletionDecision:
        matching = [obs for obs in observations if self._matches(task, obs)]

        verified = next(
            (
                obs
                for obs in matching
                if obs.success
                and obs.witness_mode
                in {
                    WitnessMode.TOOL_RECEIPT,
                    WitnessMode.PROVIDER_READBACK,
                    WitnessMode.APP_CALLBACK,
                    WitnessMode.API_WEBHOOK,
                }
            ),
            None,
        )
        if verified:
            return CompletionDecision(
                task_id=task.task_id,
                state=TaskCompletionState.PROVIDER_VERIFIED_COMPLETED,
                evidence_ref=verified.evidence_ref,
                may_continue=True,
                may_make_terminal_provider_claim=True,
                continuation_action=task.continuation_action,
                reason="completion independently witnessed by an allowed provider/app evidence mode",
                observation_id=verified.observation_id,
            )

        failed = next((obs for obs in matching if not obs.success), None)
        if failed and failed.witness_mode is not WitnessMode.USER_ASSERTION:
            return CompletionDecision(
                task_id=task.task_id,
                state=TaskCompletionState.FAILED,
                evidence_ref=failed.evidence_ref,
                may_continue=False,
                may_make_terminal_provider_claim=False,
                continuation_action=task.continuation_action,
                reason="provider/app evidence reports failure",
                observation_id=failed.observation_id,
            )

        asserted = next(
            (
                obs
                for obs in matching
                if obs.success and obs.witness_mode is WitnessMode.USER_ASSERTION
            ),
            None,
        )
        if asserted:
            safe_to_continue = (
                task.continuation_class is ContinuationClass.SAFE_INTERNAL
                and task.allow_owner_assertion_for_safe_continuation
            )
            return CompletionDecision(
                task_id=task.task_id,
                state=TaskCompletionState.OWNER_ASSERTED_COMPLETED,
                evidence_ref=asserted.evidence_ref,
                may_continue=safe_to_continue,
                may_make_terminal_provider_claim=(
                    not task.require_provider_verification_for_terminal_claim
                ),
                continuation_action=task.continuation_action,
                reason=(
                    "owner assertion accepted for safe internal continuation only"
                    if safe_to_continue
                    else "owner assertion recorded but stronger evidence is required before continuation"
                ),
                observation_id=asserted.observation_id,
            )

        return CompletionDecision(
            task_id=task.task_id,
            state=TaskCompletionState.PENDING,
            evidence_ref="",
            may_continue=False,
            may_make_terminal_provider_claim=False,
            continuation_action=task.continuation_action,
            reason="no matching completion witness has been observed",
        )

    def auto_reconcile(
        self,
        task: PendingUserTask,
        probes: Iterable[Callable[[], Optional[CompletionObservation]]],
    ) -> CompletionDecision:
        observations: List[CompletionObservation] = []
        for probe in probes:
            try:
                observation = probe()
            except Exception:
                continue
            if observation is not None:
                observations.append(observation)
        return self.reconcile(task, observations)

    @staticmethod
    def _matches(task: PendingUserTask, observation: CompletionObservation) -> bool:
        if observation.witness_mode not in task.witness_modes:
            return False
        if task.provider and observation.provider and task.provider != observation.provider:
            return False
        if task.correlation_ref and observation.correlation_ref:
            return task.correlation_ref == observation.correlation_ref
        return True


__all__ = [
    "CompletionDecision",
    "CompletionObservation",
    "CompletionWitnessEngine",
    "ContinuationClass",
    "PendingUserTask",
    "TaskCompletionState",
    "WitnessMode",
]
