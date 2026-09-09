from __future__ import annotations

"""F130 load-bearing extension of the existing Bubbles autonomic runtime.

The incumbent runtime remains the provider-local execution lifecycle.  This
extension adds only the FUSE mission-runtime terminal interlock.  The complete
owner-mission snapshot is caller-supplied by the SINGLE PRIMARY Federation
Autopilot; it is never inferred from the Bubbles provider-local work graph.
"""

from typing import Any

from bubbles.chat_governor_omega3.mission_runtime_host_v1 import MissionRuntimeHostInterlock
from bubbles.chat_governor_omega3.state import DurableState
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeSnapshot,
    RuntimeAction,
    TerminalPrepareReceipt,
)

from .autonomic_federation_runtime_base import (
    BubblesAutonomicFederationRuntime as _BaseBubblesAutonomicFederationRuntime,
    SCHEMA,
    WORK_AUTHORITY,
    WORK_EXECUTION,
    WORK_PROOF,
    WORK_READBACK,
    WORK_VALUE,
)


class BubblesAutonomicFederationRuntime(_BaseBubblesAutonomicFederationRuntime):
    """Incumbent Bubbles runtime with non-bypassable F130 terminal enforcement."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Reuse the existing ChatGov DurableState surface under the Bubbles root;
        # this is not a second mission truth store or scheduler.
        state_path = self.durable.root / "bubbles_chat_governor_omega3.sqlite3"
        self.mission_runtime = MissionRuntimeHostInterlock(DurableState(str(state_path)))

    def before_final_response(
        self,
        snapshot: MissionRuntimeSnapshot,
        *,
        now_epoch: float,
    ):
        """Evaluate the complete caller-supplied owner mission before any final response."""
        host = getattr(self, "mission_runtime", None)
        if host is None:
            raise RuntimeError("F130_MISSION_RUNTIME_HOST_NOT_BOUND")
        return host.before_final_response(snapshot, now_epoch=now_epoch)

    @staticmethod
    def _f130_decision_record(hosted) -> dict[str, Any]:
        decision = hosted.decision
        return {
            "checkpoint_id": hosted.checkpoint_id,
            "action": decision.action.value,
            "next_task_id": decision.next_task_id,
            "reasons": list(decision.reasons),
            "final_response_allowed": decision.final_response_allowed,
            "auto_continue_required": decision.auto_continue_required,
            "completion_verified": decision.completion_verified,
            "owner_guard_decision": decision.owner_guard_decision,
            "pre_final_mode": decision.pre_final_mode,
            "receipt_digest": decision.receipt_digest,
        }

    def finalize_mission_completion(
        self,
        mission,
        *,
        mission_runtime_snapshot: MissionRuntimeSnapshot | None = None,
        terminal_prepare_receipt: TerminalPrepareReceipt | None = None,
        mission_runtime_now_epoch: float = 0.0,
        **kwargs,
    ) -> dict[str, Any]:
        # All incumbent finality courts remain first and mandatory.
        incumbent = super().finalize_mission_completion(mission, **kwargs)
        if incumbent.get("state") != "MISSION_COMPLETION_VERIFIED":
            return incumbent

        reasons: list[str] = []
        if mission_runtime_snapshot is None:
            reasons.append("F130_FRESH_WHOLE_MISSION_SNAPSHOT_REQUIRED")
        if terminal_prepare_receipt is None:
            reasons.append("F130_TERMINAL_PREPARE_RECEIPT_REQUIRED")
        host = getattr(self, "mission_runtime", None)
        if host is None:
            reasons.append("F130_MISSION_RUNTIME_HOST_NOT_BOUND")
        if reasons:
            gated = dict(incumbent)
            gated.update(
                state="MISSION_RUNTIME_GATED",
                mission_value_finalized=False,
                f130_reason_codes=reasons,
            )
            gated.setdefault("truth_boundary", {})
            gated["truth_boundary"].update(
                mission_completion_requires_f130_terminal_commit=True,
                whole_mission_snapshot_is_caller_supplied_not_inferred_from_bubbles_local_graph=True,
                native_chatgpt_serving_stack_interception_proven=False,
            )
            return gated

        assert mission_runtime_snapshot is not None
        assert terminal_prepare_receipt is not None
        hosted = host.commit_terminal(
            mission_runtime_snapshot,
            terminal_prepare_receipt,
            now_epoch=mission_runtime_now_epoch,
        )
        record = self._f130_decision_record(hosted)
        if hosted.decision.action is not RuntimeAction.COMPLETE_VERIFIED or not hosted.decision.completion_verified:
            gated = dict(incumbent)
            gated.update(
                state="MISSION_RUNTIME_GATED",
                mission_value_finalized=False,
                f130_runtime_receipt=record,
                f130_reason_codes=list(hosted.decision.reasons),
            )
            gated.setdefault("truth_boundary", {})
            gated["truth_boundary"].update(
                mission_completion_requires_f130_terminal_commit=True,
                whole_mission_snapshot_is_caller_supplied_not_inferred_from_bubbles_local_graph=True,
                native_chatgpt_serving_stack_interception_proven=False,
            )
            return gated

        final = dict(incumbent)
        final["f130_runtime_receipt"] = record
        final.setdefault("truth_boundary", {})
        final["truth_boundary"].update(
            mission_completion_requires_f130_terminal_commit=True,
            f130_terminal_commit_complete_verified=True,
            whole_mission_snapshot_is_caller_supplied_not_inferred_from_bubbles_local_graph=True,
            native_chatgpt_serving_stack_interception_proven=False,
        )
        return final


__all__ = [
    "BubblesAutonomicFederationRuntime",
    "SCHEMA",
    "WORK_AUTHORITY",
    "WORK_EXECUTION",
    "WORK_PROOF",
    "WORK_READBACK",
    "WORK_VALUE",
]
