from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List


class ConversationRiskState(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    TERMINAL = "TERMINAL"


class ConversationGuardAction(str, Enum):
    CONTINUE = "CONTINUE"
    CHECKPOINT_THEN_CONTINUE = "CHECKPOINT_THEN_CONTINUE"
    CHECKPOINT_AND_MIGRATE = "CHECKPOINT_AND_MIGRATE"
    RESTORE_FROM_LAST_VERIFIED_CHECKPOINT = "RESTORE_FROM_LAST_VERIFIED_CHECKPOINT"


@dataclass(frozen=True)
class ConversationSignals:
    """Observable signals used to protect a live conversation before context exhaustion.

    ChatGPT does not expose a reliable per-conversation remaining-quota meter to this
    provider-neutral runtime. These fields therefore form a conservative operational-risk
    estimate. The resulting score must never be presented as an exact provider quota.
    """

    conversation_key: str
    substantive_turns: int = 0
    turns_since_checkpoint: int = 0
    estimated_context_chars: int = 0
    recent_tool_output_tokens: int = 0
    recent_large_outputs: int = 0
    material_deltas_uncheckpointed: int = 0
    stream_errors: int = 0
    retry_or_regeneration_count: int = 0
    attachment_count: int = 0
    large_attachment_count: int = 0
    response_latency_warning: bool = False
    namespace_bound: bool = True
    checkpoint_readback_verified: bool = True
    heavy_operation_pending: bool = False
    max_length_warning_observed: bool = False

    def __post_init__(self) -> None:
        if not self.conversation_key.strip():
            raise ValueError("conversation_key cannot be blank")
        for name, value in asdict(self).items():
            if isinstance(value, int) and not isinstance(value, bool) and value < 0:
                raise ValueError(f"{name} cannot be negative")


class ConversationExhaustionGuard:
    """Write-ahead continuity guard for long-running ChatBridge conversations.

    The guard has two independent protections:
    1. checkpoint every material delta and before every heavy operation; and
    2. pre-emptively migrate when observable risk becomes high.

    A terminal provider warning is deliberately treated differently. Once the product has
    refused further conversation turns, the runtime cannot honestly claim that a new
    same-chat checkpoint was written. Recovery must use the last independently verified
    checkpoint.
    """

    VERSION = "CEG-1.0"
    AMBER_THRESHOLD = 30
    RED_THRESHOLD = 60

    @classmethod
    def contract(cls) -> Dict[str, Any]:
        return {
            "version": cls.VERSION,
            "coverage_scope": "ALL_CHATBRIDGE_ACTIVE_CHATS",
            "quota_visibility": "NO_EXACT_PROVIDER_QUOTA_AVAILABLE",
            "score_semantics": "HEURISTIC_OPERATIONAL_RISK_NOT_PROVIDER_QUOTA",
            "write_ahead_rule": "CHECKPOINT_EVERY_MATERIAL_DELTA",
            "heavy_operation_rule": "CHECKPOINT_AND_READBACK_BEFORE_HEAVY_OPERATION",
            "amber_rule": "INCREASE_CHECKPOINT_FREQUENCY_AND_PREPARE_MIGRATION",
            "red_rule": "STOP_NONESSENTIAL_EXPANSION_CHECKPOINT_AND_MIGRATE",
            "terminal_rule": "RESTORE_FROM_LAST_VERIFIED_CHECKPOINT",
            "same_chat_terminal_checkpoint_claim": "PROHIBITED",
            "payload_rule": "POINTERS_AND_DELTAS_NOT_REPEATED_FULL_TRANSCRIPTS",
        }

    @staticmethod
    def _bounded(value: int, maximum: int) -> int:
        return max(0, min(value, maximum))

    @classmethod
    def _score(cls, signals: ConversationSignals) -> Dict[str, int]:
        return {
            "substantive_turns": cls._bounded((signals.substantive_turns // 10) * 2, 20),
            "turns_since_checkpoint": cls._bounded(signals.turns_since_checkpoint * 2, 20),
            "estimated_context_chars": cls._bounded(signals.estimated_context_chars // 25000, 18),
            "recent_tool_output_tokens": cls._bounded(signals.recent_tool_output_tokens // 1000, 14),
            "recent_large_outputs": cls._bounded(signals.recent_large_outputs * 3, 12),
            "material_deltas_uncheckpointed": cls._bounded(
                signals.material_deltas_uncheckpointed * 5, 20
            ),
            "stream_errors": cls._bounded(signals.stream_errors * 8, 16),
            "retry_or_regeneration_count": cls._bounded(
                signals.retry_or_regeneration_count * 2, 8
            ),
            "large_attachment_count": cls._bounded(signals.large_attachment_count * 2, 8),
            "response_latency_warning": 4 if signals.response_latency_warning else 0,
            "namespace_unbound": 10 if not signals.namespace_bound else 0,
            "checkpoint_readback_unverified": (
                15 if not signals.checkpoint_readback_verified else 0
            ),
            "heavy_operation_pending": 8 if signals.heavy_operation_pending else 0,
        }

    @classmethod
    def assess(cls, signals: ConversationSignals) -> Dict[str, Any]:
        if signals.max_length_warning_observed:
            return {
                "guard_version": cls.VERSION,
                "conversation_key": signals.conversation_key,
                "risk_state": ConversationRiskState.TERMINAL.value,
                "risk_score": 100,
                "score_components": {},
                "score_is_exact_provider_quota": False,
                "action": ConversationGuardAction.RESTORE_FROM_LAST_VERIFIED_CHECKPOINT.value,
                "checkpoint_required": False,
                "checkpoint_attempt_allowed": False,
                "migration_required": True,
                "new_heavy_work_allowed": False,
                "same_chat_recovery_claim_allowed": False,
                "recovery_source": "LAST_VERIFIED_CHECKPOINT",
                "reasons": ["MAX_LENGTH_WARNING_OBSERVED"],
                "signals": asdict(signals),
            }

        components = cls._score(signals)
        score = min(99, sum(components.values()))
        reasons: List[str] = [name for name, points in components.items() if points]

        forced_red = signals.stream_errors >= 2 and (
            signals.material_deltas_uncheckpointed > 0
            or signals.heavy_operation_pending
        )
        if score >= cls.RED_THRESHOLD or forced_red:
            state = ConversationRiskState.RED
        elif score >= cls.AMBER_THRESHOLD:
            state = ConversationRiskState.AMBER
        else:
            state = ConversationRiskState.GREEN

        material_checkpoint_due = signals.material_deltas_uncheckpointed > 0
        pre_heavy_checkpoint_due = signals.heavy_operation_pending
        interval_checkpoint_due = (
            state is not ConversationRiskState.GREEN
            and signals.turns_since_checkpoint >= 3
        )
        checkpoint_required = (
            material_checkpoint_due
            or pre_heavy_checkpoint_due
            or interval_checkpoint_due
            or not signals.checkpoint_readback_verified
            or not signals.namespace_bound
        )

        if state is ConversationRiskState.RED:
            action = ConversationGuardAction.CHECKPOINT_AND_MIGRATE
            migration_required = True
        elif checkpoint_required:
            action = ConversationGuardAction.CHECKPOINT_THEN_CONTINUE
            migration_required = False
        else:
            action = ConversationGuardAction.CONTINUE
            migration_required = False

        return {
            "guard_version": cls.VERSION,
            "conversation_key": signals.conversation_key,
            "risk_state": state.value,
            "risk_score": score,
            "score_components": components,
            "score_is_exact_provider_quota": False,
            "action": action.value,
            "checkpoint_required": checkpoint_required,
            "checkpoint_attempt_allowed": True,
            "checkpoint_reason": {
                "material_delta": material_checkpoint_due,
                "pre_heavy_operation": pre_heavy_checkpoint_due,
                "risk_interval": interval_checkpoint_due,
                "readback_repair": not signals.checkpoint_readback_verified,
                "namespace_binding": not signals.namespace_bound,
            },
            "migration_required": migration_required,
            "new_heavy_work_allowed": not pre_heavy_checkpoint_due,
            "same_chat_recovery_claim_allowed": True,
            "recovery_source": "CURRENT_OR_NEW_VERIFIED_CHECKPOINT",
            "reasons": reasons,
            "signals": asdict(signals),
        }

    @classmethod
    def checkpoint_metadata(
        cls,
        signals: ConversationSignals,
        assessment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return stable guard metadata suitable for HOT-state checkpointing."""
        return {
            "guard_version": cls.VERSION,
            "conversation_key": signals.conversation_key,
            "risk_state": assessment["risk_state"],
            "risk_score": assessment["risk_score"],
            "action": assessment["action"],
            "score_is_exact_provider_quota": False,
            "material_deltas_uncheckpointed": signals.material_deltas_uncheckpointed,
            "heavy_operation_pending": signals.heavy_operation_pending,
            "namespace_bound": signals.namespace_bound,
            "checkpoint_readback_verified_before_guard": (
                signals.checkpoint_readback_verified
            ),
        }
