"""Bind CFBE progress enforcement into the existing ChatGov lifecycle hook bus.

This is a composition adapter, not a new scheduler or authority plane. It makes the
existing progress governor load-bearing at PRE_TOOL/POST_TOOL when a host supplies
material state-version and before/after mission-state evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from bubbles.chat_governor_omega3.performance_kernel import (
    HookContext,
    HookDecision,
    HookEvent,
    HookResult,
    LifecycleHookBus,
)
from federation.execution_progress_governor_v1 import (
    ExecutionProgressGovernor,
    ProgressReceipt,
    StatusUpdateDecision,
    StatusUpdateGate,
)
from formation_omega.autonomic_fabric import MissionStateVector


def _vector(value: Mapping[str, Any]) -> MissionStateVector:
    return MissionStateVector(
        verified_closure=float(value.get("verified_closure", 0.0)),
        information=float(value.get("information", 0.0)),
        safety=float(value.get("safety", 0.0)),
        recoverability=float(value.get("recoverability", 0.0)),
        unlock_leverage=float(value.get("unlock_leverage", 0.0)),
    )


@dataclass(frozen=True)
class ProgressBindingReceipt:
    registered_hooks: tuple[str, ...]
    strict_state_version: bool
    native_chatgpt_binding_claimed: bool = False
    provider_effect_authorized: bool = False


class ChatGovProgressBinding:
    PRE_HOOK = "cfbe_progress_preflight_v1"
    POST_HOOK = "cfbe_progress_post_tool_v1"

    def __init__(
        self,
        *,
        governor: ExecutionProgressGovernor | None = None,
        status_gate: StatusUpdateGate | None = None,
        strict_state_version: bool = True,
    ) -> None:
        self.governor = governor or ExecutionProgressGovernor()
        self.status_gate = status_gate or StatusUpdateGate()
        self.strict_state_version = bool(strict_state_version)
        self.last_progress_receipt: ProgressReceipt | None = None

    def register(self, bus: LifecycleHookBus) -> ProgressBindingReceipt:
        bus.register(HookEvent.PRE_TOOL, self.PRE_HOOK, self.pre_tool, priority=20)
        bus.register(HookEvent.POST_TOOL, self.POST_HOOK, self.post_tool, priority=80)
        return ProgressBindingReceipt((self.PRE_HOOK, self.POST_HOOK), self.strict_state_version)

    def pre_tool(self, context: HookContext) -> HookResult:
        state_version = str(context.metadata.get("state_version", "")).strip()
        if not state_version:
            if self.strict_state_version and context.material:
                return HookResult(
                    HookDecision.DENY,
                    "MATERIAL_STATE_VERSION_REQUIRED_FOR_PROGRESS_ENFORCEMENT",
                )
            return HookResult(additional_context="PROGRESS_PRECHECK_SKIPPED_NO_STATE_VERSION")

        decision = self.governor.preflight(
            action_name=context.tool_name or "UNNAMED_TOOL",
            arguments=context.tool_args,
            state_version=state_version,
            scope_id=str(context.metadata.get("scope_id", context.mission_id)),
        )
        note = f"ACTION_FINGERPRINT:{decision.action_fingerprint};PRIOR_ZERO_PROGRESS:{decision.prior_zero_progress_attempts}"
        if not decision.allow:
            reason = decision.reason
            if decision.suggested_route:
                reason += f";SUGGESTED_ROUTE:{decision.suggested_route}"
            return HookResult(HookDecision.DENY, reason, additional_context=note)
        return HookResult(additional_context=note)

    def post_tool(self, context: HookContext) -> HookResult:
        metadata = context.metadata
        state_version = str(metadata.get("state_version", "")).strip()
        before = metadata.get("before_state")
        after = metadata.get("after_state")
        if not state_version or not isinstance(before, Mapping) or not isinstance(after, Mapping):
            return HookResult(additional_context="PROGRESS_POSTCHECK_SKIPPED_INCOMPLETE_STATE_EVIDENCE")

        receipt = self.governor.record_attempt(
            action_name=context.tool_name or "UNNAMED_TOOL",
            arguments=context.tool_args,
            state_version=state_version,
            before=_vector(before),
            after=_vector(after),
            result_summary=str(metadata.get("result_summary", "")),
            scope_id=str(metadata.get("scope_id", context.mission_id)),
        )
        self.last_progress_receipt = receipt
        note = (
            f"PROGRESS_RECEIPT:{receipt.attempt_id};DECISION:{receipt.decision};"
            f"ZERO_PROGRESS:{receipt.same_state_zero_progress_attempts}"
        )
        if receipt.decision in {
            "REQUIRE_ROUTE_MUTATION",
            "REJECT_REGRESSION_ROUTE_MUTATION_REQUIRED",
            "ESCAPE_ROUTE_REQUIRED",
        }:
            return HookResult(HookDecision.BLOCK_CONTINUE, receipt.decision, additional_context=note)
        return HookResult(additional_context=note)

    def status_update(
        self,
        *,
        state_digest: str,
        update_text: str,
        material_event: bool = False,
    ) -> StatusUpdateDecision:
        return self.status_gate.evaluate(
            state_digest=state_digest,
            update_text=update_text,
            material_event=material_event,
        )


__all__ = ["ChatGovProgressBinding", "ProgressBindingReceipt"]
