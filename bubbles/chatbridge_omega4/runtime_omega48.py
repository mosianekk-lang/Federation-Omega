from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .full_fidelity_ledger import (
    ConversationEvent,
    ConversationIdentityConflict,
    ConversationNotBound,
    EventExecutionState,
    FullFidelityConversationLedger,
    IncompleteTranscript,
    TerminalExecutionClaimError,
)
from .models import GovernanceCapsule, ProviderContinuationRef
from .operating_profile import OperatingProfile
from .runtime import ChatBridgeOmega4 as ChatBridgeOmega47
from .conversation_exhaustion import ConversationSignals


class ChatBridgeOmega48(ChatBridgeOmega47):
    """ChatBridge Ω4.8 with start-to-finish conversation capture and replay.

    Ω4.8 retains every event that an authorised ChatBridge adapter can observe in an
    append-only, hash-chained ledger. Exact restoration is claimed only when start/end
    watermarks, payloads and required artifact references are all verified. Legacy or
    partially captured chats restore in bounded mode with explicit gaps; missing context
    is never guessed.
    """

    VERSION = "CHATBRIDGE-Ω4.8-FULL-FIDELITY-CONVERSATION-LEDGER"
    CONVERSATION_LEDGER_KEY = "__chatbridge_full_fidelity_conversation_ledger__"

    def __init__(self, store) -> None:
        super().__init__(store)
        self.full_fidelity = FullFidelityConversationLedger(store.path)

    def _ledger_checkpoint(self, conversation_key: str) -> Dict[str, Any]:
        status = self.full_fidelity.status(conversation_key)
        verification = dict(status["verification"])
        return {
            "conversation_key": conversation_key,
            "namespace_key": status["namespace_key"],
            "source_provider": status["source_provider"],
            "status": status["status"],
            "verification": verification,
            "contract_version": self.full_fidelity.VERSION,
        }

    def bind_conversation_ledger(
        self,
        conversation_key: str,
        namespace: str,
        *,
        source_provider: str = "CHATGPT",
        title: str = "",
        expected_first_sequence: int = 1,
        privacy_policy: str = "GOVERNED_LOCAL_MINIMUM_NECESSARY_ACCESS",
    ) -> Dict[str, Any]:
        return self.full_fidelity.bind(
            conversation_key,
            namespace,
            source_provider=source_provider,
            title=title,
            expected_first_sequence=expected_first_sequence,
            privacy_policy=privacy_policy,
        )

    def capture_conversation_event(
        self,
        namespace: str,
        event: ConversationEvent,
        *,
        source_provider: str = "CHATGPT",
        title: str = "",
        allow_gap: bool = False,
    ) -> Dict[str, Any]:
        self.bind_conversation_ledger(
            event.conversation_key,
            namespace,
            source_provider=source_provider,
            title=title,
        )
        return self.full_fidelity.append(event, allow_gap=allow_gap)

    def capture_conversation_events(
        self,
        namespace: str,
        events: Iterable[ConversationEvent],
        *,
        source_provider: str = "CHATGPT",
        title: str = "",
        allow_gap: bool = False,
    ) -> Dict[str, Any]:
        items = list(events)
        if not items:
            return {"state": "NO_EVENTS", "captured": 0, "receipts": []}
        keys = {item.conversation_key.strip() for item in items}
        if len(keys) != 1:
            raise ConversationIdentityConflict(
                "one capture batch cannot span multiple source conversations"
            )
        self.bind_conversation_ledger(
            items[0].conversation_key,
            namespace,
            source_provider=source_provider,
            title=title,
        )
        return self.full_fidelity.append_many(items, allow_gap=allow_gap)

    def seal_conversation_ledger(
        self,
        conversation_key: str,
        *,
        expected_last_sequence: int,
        expected_first_sequence: int = 1,
        closure_reason: str = "MIGRATED_OR_COMPLETED",
        terminal_observed: bool = False,
    ) -> Dict[str, Any]:
        return self.full_fidelity.seal(
            conversation_key,
            expected_last_sequence=expected_last_sequence,
            expected_first_sequence=expected_first_sequence,
            closure_reason=closure_reason,
            terminal_observed=terminal_observed,
        )

    def verify_conversation_ledger(self, conversation_key: str) -> Dict[str, Any]:
        return self.full_fidelity.verify(conversation_key)

    def reconstruct_conversation(
        self,
        conversation_key: str,
        *,
        require_exact: bool = False,
    ) -> Dict[str, Any]:
        return self.full_fidelity.reconstruct(
            conversation_key,
            require_exact=require_exact,
        )

    def backup(
        self,
        namespace: str,
        capsule: GovernanceCapsule,
        *,
        hot_state: Dict[str, Any],
        warm_pointers: Optional[List[str]] = None,
        cold_pointers: Optional[List[str]] = None,
        provider_ref: ProviderContinuationRef = ProviderContinuationRef(),
        operating_profile: Optional[OperatingProfile] = None,
        conversation_health: Optional[Dict[str, Any]] = None,
        playbook_cursor: str = "",
        conversation_ledger_key: str = "",
    ) -> Dict[str, Any]:
        state = dict(hot_state)
        ledger_checkpoint: Dict[str, Any] = {}
        if conversation_ledger_key:
            ledger_checkpoint = self._ledger_checkpoint(conversation_ledger_key)
            state[self.CONVERSATION_LEDGER_KEY] = ledger_checkpoint
        result = super().backup(
            namespace,
            capsule,
            hot_state=state,
            warm_pointers=warm_pointers,
            cold_pointers=cold_pointers,
            provider_ref=provider_ref,
            operating_profile=operating_profile,
            conversation_health=conversation_health,
            playbook_cursor=playbook_cursor,
        )
        result["chatbridge_version"] = self.VERSION
        result["full_fidelity_ledger_checkpoint"] = ledger_checkpoint
        result["full_fidelity_contract"] = self.full_fidelity.contract()
        return result

    def refresh(
        self,
        namespace: str,
        capsule: GovernanceCapsule,
        *,
        hot_state: Dict[str, Any],
        warm_pointers: Optional[List[str]] = None,
        cold_pointers: Optional[List[str]] = None,
        provider_ref: ProviderContinuationRef = ProviderContinuationRef(),
        operating_profile: Optional[OperatingProfile] = None,
        conversation_health: Optional[Dict[str, Any]] = None,
        playbook_cursor: str = "",
        conversation_ledger_key: str = "",
    ) -> Dict[str, Any]:
        return self.backup(
            namespace,
            capsule,
            hot_state=hot_state,
            warm_pointers=warm_pointers,
            cold_pointers=cold_pointers,
            provider_ref=provider_ref,
            operating_profile=operating_profile,
            conversation_health=conversation_health,
            playbook_cursor=playbook_cursor,
            conversation_ledger_key=conversation_ledger_key,
        )

    def restore(
        self,
        namespace: str,
        *,
        destination_session_key: str,
        generation_number: Optional[int] = None,
        material_delta: bool = False,
        governance_degraded: bool = False,
        include_full_transcript: bool = True,
        require_exact_transcript: bool = False,
    ) -> Dict[str, Any]:
        payload = super().restore(
            namespace,
            destination_session_key=destination_session_key,
            generation_number=generation_number,
            material_delta=material_delta,
            governance_degraded=governance_degraded,
        )
        hot = dict(payload["hot_state"])
        checkpoint = hot.pop(self.CONVERSATION_LEDGER_KEY, None)
        payload["hot_state"] = hot
        payload["full_fidelity_ledger_checkpoint"] = (
            checkpoint if isinstance(checkpoint, dict) else {}
        )

        transcript_restore: Dict[str, Any]
        if isinstance(checkpoint, dict) and checkpoint.get("conversation_key"):
            conversation_key = str(checkpoint["conversation_key"])
            try:
                reconstructed = self.full_fidelity.reconstruct(
                    conversation_key,
                    require_exact=require_exact_transcript,
                )
                if not include_full_transcript:
                    reconstructed = {
                        key: value
                        for key, value in reconstructed.items()
                        if key != "transcript"
                    }
                transcript_restore = reconstructed
            except ConversationNotBound:
                if require_exact_transcript:
                    raise IncompleteTranscript(
                        "checkpoint references a conversation ledger that is not "
                        "available in this runtime"
                    )
                transcript_restore = {
                    "conversation_key": conversation_key,
                    "restore_mode": "LEDGER_REFERENCE_UNAVAILABLE",
                    "exact_context_complete": False,
                    "missing_ranges": "UNKNOWN_LEDGER_UNAVAILABLE",
                }
        else:
            if require_exact_transcript:
                raise IncompleteTranscript(
                    "this legacy checkpoint has no full-fidelity conversation ledger"
                )
            transcript_restore = {
                "restore_mode": "LEGACY_CHECKPOINT_NO_TRANSCRIPT_LEDGER",
                "exact_context_complete": False,
                "truth_boundary": (
                    "HOT_WARM_COLD_STATE_RESTORED_BUT_START_TO_FINISH_TRANSCRIPT_"
                    "WAS_NOT_CAPTURED"
                ),
            }

        payload["conversation_transcript_restore"] = transcript_restore
        payload["full_fidelity_ledger_required"] = True
        payload["full_fidelity_contract"] = self.full_fidelity.contract()
        payload["restore_directives"].update(
            {
                "full_fidelity_conversation_ledger": True,
                "capture_every_observed_turn": True,
                "transcript_capture_policy": self.full_fidelity.CAPTURE_POLICY,
                "transcript_restore_policy": self.full_fidelity.RESTORE_POLICY,
                "transcript_gap_policy": (
                    "EXPLICIT_MISSING_RANGES_NEVER_SYNTHESIZE_OR_GUESS"
                ),
                "artifact_manifest_policy": (
                    "STABLE_REFERENCE_HASH_AND_AVAILABILITY_REQUIRED"
                ),
                "terminal_intent_policy": "TERMINAL_INTENT_IS_NOT_EXECUTION",
            }
        )
        payload["chatbridge_version"] = self.VERSION
        return payload

    def guard_turn(
        self,
        namespace: str,
        capsule: GovernanceCapsule,
        *,
        signals: ConversationSignals,
        hot_state: Dict[str, Any],
        warm_pointers: Optional[List[str]] = None,
        cold_pointers: Optional[List[str]] = None,
        provider_ref: ProviderContinuationRef = ProviderContinuationRef(),
        operating_profile: Optional[OperatingProfile] = None,
        playbook_cursor: str = "",
        conversation_event: Optional[ConversationEvent] = None,
        conversation_ledger_key: str = "",
        conversation_title: str = "",
        source_provider: str = "CHATGPT",
    ) -> Dict[str, Any]:
        """Capture the current turn before applying the Ω4.7 exhaustion guard.

        The provider adapter should call this for every observed user/assistant/system
        message and every tool/provider event. If the native product has already shown a
        terminal warning, an event cannot be represented as executed unless separate
        provider proof exists.
        """
        ledger_key = conversation_ledger_key.strip()
        capture_receipt: Dict[str, Any] = {}
        terminal_seal: Dict[str, Any] = {}

        if conversation_event is not None:
            if conversation_event.conversation_key.strip() != signals.conversation_key.strip():
                raise ConversationIdentityConflict(
                    "conversation event and health signals refer to different source chats"
                )
            if (
                signals.max_length_warning_observed
                and conversation_event.execution_state
                == EventExecutionState.EXECUTED_VERIFIED
            ):
                raise TerminalExecutionClaimError(
                    "an event observed after the terminal product warning cannot be "
                    "claimed executed without separate provider proof"
                )
            capture_receipt = self.capture_conversation_event(
                namespace,
                conversation_event,
                source_provider=source_provider,
                title=conversation_title,
            )
            ledger_key = conversation_event.conversation_key.strip()
            if signals.max_length_warning_observed:
                terminal_seal = self.seal_conversation_ledger(
                    ledger_key,
                    expected_last_sequence=conversation_event.sequence,
                    closure_reason="PROVIDER_MAXIMUM_CONVERSATION_LENGTH",
                    terminal_observed=True,
                )

        guarded_hot = dict(hot_state)
        if ledger_key:
            guarded_hot[self.CONVERSATION_LEDGER_KEY] = self._ledger_checkpoint(
                ledger_key
            )

        result = super().guard_turn(
            namespace,
            capsule,
            signals=signals,
            hot_state=guarded_hot,
            warm_pointers=warm_pointers,
            cold_pointers=cold_pointers,
            provider_ref=provider_ref,
            operating_profile=operating_profile,
            playbook_cursor=playbook_cursor,
        )
        result["chatbridge_version"] = self.VERSION
        result["conversation_capture"] = capture_receipt
        result["conversation_terminal_seal"] = terminal_seal
        result["full_fidelity_contract"] = self.full_fidelity.contract()
        return result
