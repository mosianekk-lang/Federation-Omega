"""Execution-continuity binding for Frontier Convergence.

This module deliberately reuses the Federation's existing ChatBridge Conversation
Exhaustion Guard and EvidenceOps Chat Failure Resilience Engine (CFRE Ω). It does
not create a parallel recovery institution and it does not control ChatGPT,
browser, network, or provider runtimes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from bubbles.chatbridge_omega4.conversation_exhaustion import (
    ConversationExhaustionGuard,
    ConversationSignals,
)
from evidenceops.build_system.chat_failure_resilience import (
    build_checkpoint,
    classify_failure,
)


@dataclass(frozen=True)
class PayloadGovernanceReceipt:
    mode: str
    original_chars: int
    returned_chars: int
    omitted_chars: int
    marker_hits: tuple[str, ...]
    text: str


class ToolPayloadCircuitBreaker:
    """Keep large tool/log payloads out of conversational control surfaces.

    Small payloads pass through. Large payloads are reduced to a bounded window
    around failure/exception markers. Raw evidence should remain in its durable
    provider/artifact store and be referenced separately.
    """

    DEFAULT_MARKERS = (
        "FAIL",
        "ERROR",
        "AssertionError",
        "Traceback",
        "Exception",
        "MISMATCH",
    )

    @classmethod
    def govern(
        cls,
        text: str,
        *,
        hard_char_limit: int = 12000,
        context_lines: int = 2,
        markers: Sequence[str] | None = None,
    ) -> PayloadGovernanceReceipt:
        value = str(text)
        limit = max(512, int(hard_char_limit))
        if len(value) <= limit:
            return PayloadGovernanceReceipt(
                mode="PASS_THROUGH",
                original_chars=len(value),
                returned_chars=len(value),
                omitted_chars=0,
                marker_hits=(),
                text=value,
            )

        selected_markers = tuple(markers or cls.DEFAULT_MARKERS)
        lines = value.splitlines()
        selected_indexes: set[int] = set()
        marker_hits: set[str] = set()
        for idx, line in enumerate(lines):
            for marker in selected_markers:
                if marker.casefold() in line.casefold():
                    marker_hits.add(marker)
                    start = max(0, idx - max(0, int(context_lines)))
                    end = min(len(lines), idx + max(0, int(context_lines)) + 1)
                    selected_indexes.update(range(start, end))

        if selected_indexes:
            bounded = "\n".join(lines[idx] for idx in sorted(selected_indexes))
        else:
            # Preserve both ends when no useful marker exists.
            half = max(1, limit // 2)
            bounded = value[:half] + "\n...[PAYLOAD_GOVERNED]...\n" + value[-half:]

        if len(bounded) > limit:
            bounded = bounded[:limit] + "\n...[PAYLOAD_GOVERNED_TRUNCATED]"

        return PayloadGovernanceReceipt(
            mode="BOUNDED_EXCEPTION_WINDOW",
            original_chars=len(value),
            returned_chars=len(bounded),
            omitted_chars=max(0, len(value) - len(bounded)),
            marker_hits=tuple(sorted(marker_hits)),
            text=bounded,
        )


class FederationExecutionContinuityAdapter:
    """Bind Frontier missions to ChatBridge/CFRE continuity controls."""

    @staticmethod
    def preflight(
        *,
        conversation_key: str,
        substantive_turns: int = 0,
        turns_since_checkpoint: int = 0,
        estimated_context_chars: int = 0,
        recent_tool_output_tokens: int = 0,
        recent_large_outputs: int = 0,
        material_deltas_uncheckpointed: int = 0,
        stream_errors: int = 0,
        retry_or_regeneration_count: int = 0,
        checkpoint_readback_verified: bool = True,
        namespace_bound: bool = True,
        heavy_operation_pending: bool = False,
        max_length_warning_observed: bool = False,
    ) -> dict[str, Any]:
        signals = ConversationSignals(
            conversation_key=conversation_key,
            substantive_turns=substantive_turns,
            turns_since_checkpoint=turns_since_checkpoint,
            estimated_context_chars=estimated_context_chars,
            recent_tool_output_tokens=recent_tool_output_tokens,
            recent_large_outputs=recent_large_outputs,
            material_deltas_uncheckpointed=material_deltas_uncheckpointed,
            stream_errors=stream_errors,
            retry_or_regeneration_count=retry_or_regeneration_count,
            checkpoint_readback_verified=checkpoint_readback_verified,
            namespace_bound=namespace_bound,
            heavy_operation_pending=heavy_operation_pending,
            max_length_warning_observed=max_length_warning_observed,
        )
        assessment = ConversationExhaustionGuard.assess(signals)
        return {
            "assessment": assessment,
            "guard_checkpoint_metadata": ConversationExhaustionGuard.checkpoint_metadata(
                signals, assessment
            ),
        }

    @staticmethod
    def write_ahead_checkpoint(
        *,
        active_directive: str,
        objective: str,
        last_proven_state: str,
        last_completed_action: str,
        next_pending_action: str,
        active_artifacts: Sequence[str] = (),
        active_dependencies: Sequence[str] = (),
        conversation_id: str | None = None,
        source_turn_id: str | None = None,
        tool_inflight: bool = False,
        tool_call_id: str | None = None,
        previous: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "active_directive": active_directive,
            "objective": objective,
            "last_proven_state": last_proven_state,
            "last_completed_action": last_completed_action,
            "next_pending_action": next_pending_action,
            "active_artifacts": list(active_artifacts),
            "active_dependencies": list(active_dependencies),
            "conversation_id": conversation_id,
            "source_turn_id": source_turn_id,
            "tool_inflight": bool(tool_inflight),
            "tool_call_id": tool_call_id,
        }
        return build_checkpoint(event, dict(previous or {}))

    @staticmethod
    def diagnose_failure(
        event: Mapping[str, Any],
        *,
        previous_checkpoint: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_dict = dict(event)
        candidates = classify_failure(event_dict)
        checkpoint = build_checkpoint(event_dict, dict(previous_checkpoint or {}))
        primary = candidates[0]
        return {
            "failure_class": primary.failure_class,
            "confidence": primary.score,
            "signals": primary.signals,
            "dependencies": primary.dependencies,
            "candidates": [asdict(item) for item in candidates],
            "checkpoint": checkpoint,
            "retry_rule": (
                "READBACK_BEFORE_RETRY"
                if primary.failure_class == "TOOL_OR_CONNECTOR_FAILURE"
                else "RESUME_FROM_LAST_PROVEN_CHECKPOINT"
            ),
        }
