from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .alpha_omega_capture import (
    AlphaOmegaConversationCapture,
    CaptureObservation,
    CapturePath,
    StreamExpectation,
)
from .conversation_exhaustion import ConversationSignals
from .full_fidelity_ledger import (
    ConversationEvent,
    ConversationIdentityConflict,
    EventExecutionState,
    IncompleteTranscript,
    TerminalExecutionClaimError,
)
from .models import GovernanceCapsule, ProviderContinuationRef
from .operating_profile import OperatingProfile
from .runtime_omega48 import ChatBridgeOmega48


class ChatBridgeOmega49(ChatBridgeOmega48):
    """ChatBridge Ω4.9 with Alpha→Omega multi-path/multi-stream assurance.

    Ω4.9 retains Ω4.8's full-fidelity hash-chained ledger and adds independent capture
    path registration, failover routing, stream watermarks, conflict quarantine,
    multi-path corroboration, a completion witness and token-bounded replay chunks.
    Source completeness is distinct from provider deployment: a live browser/API/App
    adapter must still deliver every native event for universal coverage.
    """

    VERSION = "CHATBRIDGE-Ω4.9-ALPHA-OMEGA-MULTIPATH-MULTISTREAM"
    ALPHA_OMEGA_CAPTURE_KEY = "__chatbridge_alpha_omega_capture_checkpoint__"

    def __init__(self, store) -> None:
        super().__init__(store)
        self.alpha_omega_capture = AlphaOmegaConversationCapture(
            store.path,
            self.full_fidelity,
        )

    def register_capture_path(self, path: CapturePath) -> Dict[str, Any]:
        return self.alpha_omega_capture.register_path(path)

    def rank_capture_paths(self, conversation_key: str) -> List[Dict[str, Any]]:
        return self.alpha_omega_capture.rank_paths(conversation_key)

    def declare_stream_expectations(
        self,
        conversation_key: str,
        expectations: Iterable[StreamExpectation],
    ) -> Dict[str, Any]:
        return self.alpha_omega_capture.declare_stream_expectations(
            conversation_key,
            expectations,
        )

    def capture_multipath_stream_events(
        self,
        observations: Iterable[CaptureObservation],
        *,
        allow_derived_ordering: bool = True,
        source_provider: str = "CHATGPT",
        title: str = "",
    ) -> Dict[str, Any]:
        return self.alpha_omega_capture.capture(
            observations,
            allow_derived_ordering=allow_derived_ordering,
            source_provider=source_provider,
            title=title,
        )

    def reconcile_multipath_stream_capture(
        self,
        conversation_key: str,
        namespace_key: str,
        *,
        allow_derived_ordering: bool = True,
        source_provider: str = "CHATGPT",
        title: str = "",
    ) -> Dict[str, Any]:
        return self.alpha_omega_capture.reconcile(
            conversation_key,
            namespace_key,
            allow_derived_ordering=allow_derived_ordering,
            source_provider=source_provider,
            title=title,
        )

    def finalize_multipath_stream_capture(
        self,
        conversation_key: str,
        namespace_key: str,
        *,
        expected_last_sequence: int,
        expected_first_sequence: int = 1,
        closure_reason: str = "PREEMPTIVE_MIGRATION_OR_COMPLETION",
        terminal_observed: bool = False,
        allow_derived_ordering: bool = True,
    ) -> Dict[str, Any]:
        return self.alpha_omega_capture.finalize(
            conversation_key,
            namespace_key,
            expected_last_sequence=expected_last_sequence,
            expected_first_sequence=expected_first_sequence,
            closure_reason=closure_reason,
            terminal_observed=terminal_observed,
            allow_derived_ordering=allow_derived_ordering,
        )

    def assess_multipath_stream_capture(self, conversation_key: str) -> Dict[str, Any]:
        return self.alpha_omega_capture.assess(conversation_key)

    def reconstruct_conversation(
        self,
        conversation_key: str,
        *,
        require_exact: bool = False,
        require_alpha_omega_exact: Optional[bool] = None,
        replay_token_limit: int = 3800,
    ) -> Dict[str, Any]:
        exact = require_exact if require_alpha_omega_exact is None else require_alpha_omega_exact
        return self.alpha_omega_capture.reconstruct(
            conversation_key,
            require_alpha_omega_exact=exact,
            replay_token_limit=replay_token_limit,
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
        alpha_omega_checkpoint: Dict[str, Any] = {}
        if conversation_ledger_key:
            alpha_omega_checkpoint = self.alpha_omega_capture.checkpoint(
                conversation_ledger_key
            )
            state[self.ALPHA_OMEGA_CAPTURE_KEY] = alpha_omega_checkpoint
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
            conversation_ledger_key=conversation_ledger_key,
        )
        result["chatbridge_version"] = self.VERSION
        result["alpha_omega_capture_checkpoint"] = alpha_omega_checkpoint
        result["alpha_omega_capture_contract"] = (
            self.alpha_omega_capture.contract()
        )
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
        require_alpha_omega_exact: Optional[bool] = None,
        replay_token_limit: int = 3800,
    ) -> Dict[str, Any]:
        payload = super().restore(
            namespace,
            destination_session_key=destination_session_key,
            generation_number=generation_number,
            material_delta=material_delta,
            governance_degraded=governance_degraded,
            include_full_transcript=include_full_transcript,
            require_exact_transcript=require_exact_transcript,
        )
        hot = dict(payload["hot_state"])
        checkpoint = hot.pop(self.ALPHA_OMEGA_CAPTURE_KEY, None)
        payload["hot_state"] = hot
        payload["alpha_omega_capture_checkpoint"] = (
            checkpoint if isinstance(checkpoint, dict) else {}
        )

        exact_required = (
            require_exact_transcript
            if require_alpha_omega_exact is None
            else require_alpha_omega_exact
        )
        conversation_key = ""
        if isinstance(checkpoint, dict):
            conversation_key = str(checkpoint.get("conversation_key", ""))
        if not conversation_key:
            ffcl_checkpoint = payload.get("full_fidelity_ledger_checkpoint", {})
            if isinstance(ffcl_checkpoint, dict):
                conversation_key = str(ffcl_checkpoint.get("conversation_key", ""))

        if conversation_key:
            try:
                reconstruction = self.alpha_omega_capture.reconstruct(
                    conversation_key,
                    require_alpha_omega_exact=bool(exact_required),
                    replay_token_limit=replay_token_limit,
                )
                if not include_full_transcript:
                    reconstruction = {
                        key: value
                        for key, value in reconstruction.items()
                        if key not in {"transcript", "replay_chunks"}
                    }
                payload["alpha_omega_conversation_restore"] = reconstruction
            except IncompleteTranscript:
                if exact_required:
                    raise
                payload["alpha_omega_conversation_restore"] = {
                    "conversation_key": conversation_key,
                    "restore_mode": "BOUNDED_ALPHA_OMEGA_RESTORE",
                    "exact_alpha_omega_complete": False,
                    "assessment": self.alpha_omega_capture.assess(
                        conversation_key
                    ),
                }
        else:
            if exact_required:
                raise IncompleteTranscript(
                    "the selected generation has no Alpha→Omega capture checkpoint"
                )
            payload["alpha_omega_conversation_restore"] = {
                "restore_mode": "LEGACY_NO_ALPHA_OMEGA_CAPTURE_CHECKPOINT",
                "exact_alpha_omega_complete": False,
                "truth_boundary": (
                    "CHECKPOINT_STATE_MAY_BE_RESTORED_BUT_MULTIPATH_MULTISTREAM_"
                    "START_TO_FINISH_ASSURANCE_WAS_NOT_CAPTURED"
                ),
            }

        payload["restore_directives"].update(
            {
                "alpha_omega_multipath_multistream": True,
                "exact_source_conversation_identity_first": True,
                "register_independent_capture_paths": True,
                "preserve_stream_watermarks": True,
                "fail_closed_on_path_or_stream_conflict": True,
                "route_failure_is_not_objective_failure": True,
                "use_ranked_path_failover": True,
                "exact_promotion_requires_multipath_stream_completion_witness": True,
                "replay_token_limit": replay_token_limit,
            }
        )
        payload["alpha_omega_capture_contract"] = (
            self.alpha_omega_capture.contract()
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
        capture_observation: Optional[CaptureObservation] = None,
        capture_path: Optional[CapturePath] = None,
        conversation_title: str = "",
        source_provider: str = "CHATGPT",
    ) -> Dict[str, Any]:
        multipath_capture: Dict[str, Any] = {}
        terminal_finalization: Dict[str, Any] = {}
        ledger_key = ""

        if capture_observation is not None:
            if conversation_event is not None:
                raise ConversationIdentityConflict(
                    "supply either a legacy conversation_event or a multi-path capture_observation, not both"
                )
            if (
                capture_observation.conversation_key.strip()
                != signals.conversation_key.strip()
            ):
                raise ConversationIdentityConflict(
                    "capture observation and health signals refer to different source conversations"
                )
            if (
                signals.max_length_warning_observed
                and capture_observation.execution_state
                == EventExecutionState.EXECUTED_VERIFIED
            ):
                raise TerminalExecutionClaimError(
                    "an event observed after the terminal warning cannot be called executed without separate provider proof"
                )
            if capture_path is not None:
                if (
                    capture_path.conversation_key.strip()
                    != capture_observation.conversation_key.strip()
                    or capture_path.path_id.strip()
                    != capture_observation.path_id.strip()
                ):
                    raise ConversationIdentityConflict(
                        "capture path and observation identity do not match"
                    )
                self.register_capture_path(capture_path)
            multipath_capture = self.capture_multipath_stream_events(
                [capture_observation],
                source_provider=source_provider,
                title=conversation_title,
            )
            ledger_key = capture_observation.conversation_key.strip()
            if signals.max_length_warning_observed:
                verification = self.verify_conversation_ledger(ledger_key)
                last_sequence = int(verification.get("last_sequence") or 0)
                if last_sequence:
                    terminal_finalization = self.finalize_multipath_stream_capture(
                        ledger_key,
                        capture_observation.namespace_key,
                        expected_last_sequence=last_sequence,
                        closure_reason="PROVIDER_MAXIMUM_CONVERSATION_LENGTH",
                        terminal_observed=True,
                    )

        if not ledger_key:
            ledger_key = conversation_ledger_key.strip()

        result = super().guard_turn(
            namespace,
            capsule,
            signals=signals,
            hot_state=hot_state,
            warm_pointers=warm_pointers,
            cold_pointers=cold_pointers,
            provider_ref=provider_ref,
            operating_profile=operating_profile,
            playbook_cursor=playbook_cursor,
            conversation_event=(None if capture_observation is not None else conversation_event),
            conversation_ledger_key=ledger_key,
            conversation_title=conversation_title,
            source_provider=source_provider,
        )
        result["chatbridge_version"] = self.VERSION
        result["alpha_omega_multipath_capture"] = multipath_capture
        result["alpha_omega_terminal_finalization"] = terminal_finalization
        result["alpha_omega_capture_contract"] = (
            self.alpha_omega_capture.contract()
        )
        return result


__all__ = ["ChatBridgeOmega49"]
