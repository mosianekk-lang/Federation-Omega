from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import uuid
from dataclasses import replace
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ao_harmonic_v3.science_and_routes import FormationEngine
from .full_fidelity_ledger import (
    ConversationIdentityConflict, ConversationNotBound, EventExecutionState,
    FullFidelityConversationLedger, IncompleteTranscript,
    TerminalExecutionClaimError, TranscriptIntegrityState,
)
from .alpha_omega_models import (
    AlphaOmegaRestoreMode, CaptureObservation, CapturePath, CapturePathConflict,
    CapturePathKind, CapturePathNotRegistered, CapturePathState, ConversationStream,
    ObservationConflict, OrderingAuthority, ReconciliationState, ReplayChunk,
    StreamExpectation, StreamManifestError, _canonical_json, _digest, _key,
    _missing_ranges, _namespace, _now,
)

class AlphaOmegaReplayMixin:
    @staticmethod
    def _estimate_tokens(value: Any) -> int:
        return max(1, math.ceil(len(_canonical_json(value)) / 4.0))

    @classmethod
    def build_replay_chunks(
        cls,
        transcript: Sequence[Dict[str, Any]],
        *,
        token_limit: int = 3800,
    ) -> List[Dict[str, Any]]:
        if token_limit < 500:
            raise ValueError("token_limit must be >= 500")
        chunks: List[ReplayChunk] = []
        current: List[Dict[str, Any]] = []
        current_tokens = 0
        current_first = 0
        current_last = 0

        def flush(*, continues_event: bool = False) -> None:
            nonlocal current, current_tokens, current_first, current_last
            if not current:
                return
            payload = tuple(current)
            chunks.append(
                ReplayChunk(
                    chunk_id=f"ao_replay_{len(chunks) + 1:05d}",
                    first_sequence=current_first,
                    last_sequence=current_last,
                    estimated_tokens=current_tokens,
                    payload=payload,
                    chunk_sha256=_digest(payload),
                    continues_event=continues_event,
                )
            )
            current = []
            current_tokens = 0
            current_first = 0
            current_last = 0

        safe_limit = token_limit - 160
        for event in transcript:
            sequence = int(event.get("sequence", 0) or 0)
            event_tokens = cls._estimate_tokens(event)
            if event_tokens <= safe_limit:
                if current and current_tokens + event_tokens > safe_limit:
                    flush()
                if not current:
                    current_first = sequence
                current.append(dict(event))
                current_last = sequence
                current_tokens += event_tokens
                continue

            flush()
            content_json = _canonical_json(event.get("content"))
            original_hash = hashlib.sha256(content_json.encode("utf-8")).hexdigest()
            base = {key: value for key, value in event.items() if key != "content"}
            base_tokens = cls._estimate_tokens(base) + 120
            char_budget = max(256, (safe_limit - base_tokens) * 4)
            fragments = [
                content_json[index : index + char_budget]
                for index in range(0, len(content_json), char_budget)
            ]
            for index, fragment in enumerate(fragments, 1):
                payload = {
                    **base,
                    "content_fragment": fragment,
                    "fragment_index": index,
                    "fragment_count": len(fragments),
                    "original_content_sha256": original_hash,
                    "fragment_policy": "REASSEMBLE_JSON_TEXT_BEFORE_EVENT_REPLAY",
                }
                current = [payload]
                current_first = sequence
                current_last = sequence
                current_tokens = cls._estimate_tokens(payload)
                flush(continues_event=index < len(fragments))
        flush()
        return [chunk.to_dict() for chunk in chunks]

    def reconstruct(
        self,
        conversation_key: str,
        *,
        require_alpha_omega_exact: bool = False,
        replay_token_limit: int = 3800,
    ) -> Dict[str, Any]:
        assessment = self.assess(conversation_key)
        if require_alpha_omega_exact and not assessment.get("exact_alpha_omega_complete"):
            raise IncompleteTranscript(
                "exact Alpha→Omega start-to-finish restore is unavailable; inspect FFCL gaps, stream manifest, path corroboration and open findings"
            )
        if assessment["restore_mode"] == AlphaOmegaRestoreMode.REJECT_CONFLICTED.value:
            raise ObservationConflict(
                "conversation capture contains an unresolved critical conflict"
            )
        reconstructed = self.ledger.reconstruct(
            conversation_key,
            require_exact=False,
        )
        chunks = self.build_replay_chunks(
            reconstructed["transcript"],
            token_limit=replay_token_limit,
        )
        return {
            **reconstructed,
            "alpha_omega_assessment": assessment,
            "alpha_omega_restore_mode": assessment["restore_mode"],
            "exact_alpha_omega_complete": assessment.get(
                "exact_alpha_omega_complete", False
            ),
            "replay_chunks": chunks,
            "replay_contract": {
                "token_limit": replay_token_limit,
                "event_order": "CANONICAL_SEQUENCE_ASCENDING",
                "chunk_integrity": "SHA256_CANONICAL_CHUNK",
                "oversized_event_policy": "FRAGMENT_AND_REASSEMBLE_WITH_ORIGINAL_CONTENT_HASH",
                "gap_policy": "NEVER_SYNTHESIZE_MISSING_CONTENT",
            },
        }

    def checkpoint(self, conversation_key: str) -> Dict[str, Any]:
        assessment = self.assess(conversation_key)
        return {
            "conversation_key": conversation_key,
            "namespace_key": assessment.get("namespace_key", ""),
            "engine_version": self.VERSION,
            "restore_mode": assessment.get("restore_mode"),
            "exact_alpha_omega_complete": assessment.get(
                "exact_alpha_omega_complete", False
            ),
            "ffcl_chain_head_hash": assessment.get("ffcl", {}).get(
                "chain_head_hash", ""
            ),
            "ffcl_merkle_root": assessment.get("ffcl", {}).get("merkle_root", ""),
            "canonical_event_count": assessment.get("canonical_event_count", 0),
            "derived_ordering_count": assessment.get("derived_ordering_count", 0),
            "minimum_independent_groups_per_event": assessment.get(
                "minimum_independent_groups_per_event", 0
            ),
            "stream_assurance": assessment.get("stream_assurance", {}),
            "open_findings": assessment.get("open_findings", []),
            "next_acquisition_routes": assessment.get("next_acquisition_routes", []),
            "contract": self.contract(),
        }

    @classmethod
    def contract(cls) -> Dict[str, Any]:
        return {
            "version": cls.VERSION,
            "chatbridge_version": cls.CHATBRIDGE_VERSION,
            "architecture_cycle": list(cls.ARCHITECTURE_CYCLE),
            "alpha": "BIND_EXACT_CONVERSATION_NAMESPACE_PATHS_STREAMS_AND_WATERMARKS",
            "paths": "REGISTER_RANK_FAILOVER_AND_CORROBORATE_INDEPENDENT_CAPTURE_ROUTES",
            "streams": "PRESERVE_USER_ASSISTANT_SYSTEM_TOOL_CONNECTOR_ATTACHMENT_DECISION_CORRECTION_AND_TERMINAL_LANES",
            "reconciliation": "DEDUPE_IDENTICAL_OBSERVATIONS_QUARANTINE_CONFLICTS_NEVER_SILENTLY_CHOOSE",
            "ordering": "EXPLICIT_GLOBAL_SEQUENCE_REQUIRED_FOR_ALPHA_OMEGA_EXACT_PROMOTION",
            "canonical_store": "FFCL_APPEND_ONLY_HASH_CHAIN_AND_MERKLE_ROOT",
            "omega": "COMPLETION_WITNESS_REQUIRES_EXACT_FFCL_COMPLETE_STREAMS_AND_MULTIPATH_CORROBORATION",
            "failover": "ROUTE_FAILURE_IS_NOT_OBJECTIVE_FAILURE_USE_NEXT_RANKED_ELIGIBLE_PATH",
            "replay": "TOKEN_BOUNDED_SEQUENCE_PRESERVING_HASHED_CHUNKS",
            "terminal": "TERMINAL_INTENT_IS_NOT_EXECUTION",
            "legacy": "IMPORT_AVAILABLE_PRIMARY_SOURCES_MARK_GAPS_NEVER_GUESS",
            "provider_boundary": "SOURCE_RUNTIME_REQUIRES_AN_AUTHORISED_EVENT_ADAPTER_FOR_LIVE_NATIVE_COVERAGE",
        }


__all__ = [
    "AlphaOmegaCaptureError",
    "AlphaOmegaConversationCapture",
    "AlphaOmegaRestoreMode",
    "CaptureObservation",
    "CapturePath",
    "CapturePathConflict",
    "CapturePathKind",
    "CapturePathNotRegistered",
    "CapturePathState",
    "ConversationStream",
    "ObservationConflict",
    "OrderingAuthority",
    "ReconciliationState",
    "ReplayChunk",
    "StreamExpectation",
    "StreamManifestError",
]
