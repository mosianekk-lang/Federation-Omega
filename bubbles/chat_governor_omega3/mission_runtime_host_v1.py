"""ChatGov/Bubbles host adapter for the FUSE mission-runtime interlock.

The host adapter persists every pre-final and terminal-commit decision through the
existing ChatGov DurableState. It does not create a scheduler or provider runtime;
callers remain responsible for dispatching the returned next_task_id and for making
final-response emission conditional on final_response_allowed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from bubbles.chat_governor_omega3.state import DurableState
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeDecision,
    MissionRuntimeInterlock,
    MissionRuntimeSnapshot,
    TerminalPrepareReceipt,
)

HOST_SCHEMA = "FUSE-MISSION-RUNTIME-HOST-BINDING-V1"
HOST_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class HostedMissionRuntimeReceipt:
    schema: str
    version: str
    mission_id: str
    checkpoint_id: str
    decision: MissionRuntimeDecision
    final_response_allowed: bool
    auto_continue_required: bool


class MissionRuntimeHostInterlock:
    """Durable host-side pre-final/terminal-commit enforcement adapter."""

    def __init__(
        self,
        state: DurableState,
        interlock: MissionRuntimeInterlock | None = None,
    ) -> None:
        self.state = state
        self.interlock = interlock or MissionRuntimeInterlock()

    def before_final_response(
        self,
        snapshot: MissionRuntimeSnapshot,
        *,
        now_epoch: float,
    ) -> HostedMissionRuntimeReceipt:
        decision = self.interlock.decide(snapshot, now_epoch=now_epoch)
        return self._persist(snapshot, decision, event="MISSION_RUNTIME_PRE_FINAL")

    def commit_terminal(
        self,
        snapshot: MissionRuntimeSnapshot,
        prepare: TerminalPrepareReceipt,
        *,
        now_epoch: float,
    ) -> HostedMissionRuntimeReceipt:
        decision = self.interlock.commit_terminal(
            snapshot,
            prepare,
            now_epoch=now_epoch,
        )
        return self._persist(snapshot, decision, event="MISSION_RUNTIME_TERMINAL_COMMIT")

    def _persist(
        self,
        snapshot: MissionRuntimeSnapshot,
        decision: MissionRuntimeDecision,
        *,
        event: str,
    ) -> HostedMissionRuntimeReceipt:
        checkpoint_id = self.state.checkpoint(
            snapshot.mission_id,
            {
                "event": event,
                "host_schema": HOST_SCHEMA,
                "host_version": HOST_VERSION,
                "contract_epoch": snapshot.contract_epoch,
                "ledger_tail": snapshot.ledger_tail,
                "decision": asdict(decision),
            },
            proof_bearing=bool(decision.completion_verified),
        )
        self.state.update_metric(
            "fuse.mission_runtime.final_allowed",
            1.0 if decision.final_response_allowed else 0.0,
        )
        self.state.update_metric(
            "fuse.mission_runtime.auto_continue",
            1.0 if decision.auto_continue_required else 0.0,
        )
        self.state.update_metric(
            "fuse.mission_runtime.complete_verified",
            1.0 if decision.completion_verified else 0.0,
        )
        return HostedMissionRuntimeReceipt(
            schema=HOST_SCHEMA,
            version=HOST_VERSION,
            mission_id=snapshot.mission_id,
            checkpoint_id=checkpoint_id,
            decision=decision,
            final_response_allowed=decision.final_response_allowed,
            auto_continue_required=decision.auto_continue_required,
        )


__all__ = [
    "HOST_SCHEMA",
    "HOST_VERSION",
    "HostedMissionRuntimeReceipt",
    "MissionRuntimeHostInterlock",
]
