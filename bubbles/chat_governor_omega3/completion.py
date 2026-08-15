from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from bubbles.chatbridge_omega4.completion_witness import (
    CompletionDecision,
    CompletionObservation,
    CompletionWitnessEngine,
    PendingUserTask,
    TaskCompletionState,
)

from .state import DurableState


@dataclass(frozen=True)
class CompletionReconcileResult:
    decision: CompletionDecision
    checkpoint_id: str
    stale_blocker_cleared: bool
    auto_resume_safe: bool


class ChatGovCompletionInterlock:
    """ChatGov-side policy adapter for ChatBridge completion witnessing.

    Pending owner tasks are reconciled before a repeated user prompt. Provider/app
    proof can clear a blocker. Owner assertion can clear a blocker only when the
    underlying CompletionWitnessEngine decision says safe internal continuation is
    allowed. Consequential authority is never created by this adapter.
    """

    def __init__(self, state: DurableState, engine: Optional[CompletionWitnessEngine] = None) -> None:
        self.state = state
        self.engine = engine or CompletionWitnessEngine()

    def reconcile(
        self,
        mission_id: str,
        task: PendingUserTask,
        observations: Iterable[CompletionObservation],
        *,
        trigger: str,
    ) -> CompletionReconcileResult:
        decision = self.engine.reconcile(task, observations)
        cleared = decision.state in {
            TaskCompletionState.OWNER_ASSERTED_COMPLETED,
            TaskCompletionState.PROVIDER_VERIFIED_COMPLETED,
        } and decision.may_continue
        checkpoint_id = self.state.checkpoint(
            mission_id,
            {
                "event": "USER_TASK_COMPLETION_RECONCILED",
                "trigger": trigger,
                "task_id": task.task_id,
                "task_type": task.task_type,
                "state": decision.state.value,
                "evidence_ref": decision.evidence_ref,
                "observation_id": decision.observation_id,
                "stale_blocker_cleared": cleared,
                "auto_resume_safe": bool(decision.may_continue),
                "terminal_provider_claim_allowed": bool(decision.may_make_terminal_provider_claim),
                "continuation_action": decision.continuation_action,
            },
            proof_bearing=(
                decision.state is TaskCompletionState.PROVIDER_VERIFIED_COMPLETED
            ),
        )
        return CompletionReconcileResult(
            decision=decision,
            checkpoint_id=checkpoint_id,
            stale_blocker_cleared=cleared,
            auto_resume_safe=bool(decision.may_continue),
        )

    def auto_reconcile(
        self,
        mission_id: str,
        task: PendingUserTask,
        probes: Iterable[Callable[[], Optional[CompletionObservation]]],
        *,
        trigger: str,
    ) -> CompletionReconcileResult:
        observations = []
        for probe in probes:
            try:
                observation = probe()
            except Exception:
                continue
            if observation is not None:
                observations.append(observation)
        return self.reconcile(mission_id, task, observations, trigger=trigger)

    def before_user_prompt(
        self,
        mission_id: str,
        task: PendingUserTask,
        probes: Iterable[Callable[[], Optional[CompletionObservation]]],
    ) -> CompletionReconcileResult:
        """Mandatory PRE_USER_PROMPT reconciliation point."""
        return self.auto_reconcile(
            mission_id,
            task,
            probes,
            trigger="PRE_USER_PROMPT",
        )


__all__ = ["ChatGovCompletionInterlock", "CompletionReconcileResult"]
