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

class AlphaOmegaAssessMixin:
    def _stream_assessment(self, conversation_key: str) -> Dict[str, Any]:
        conn = self._conn()
        expectation_rows = conn.execute(
            """
            SELECT * FROM ao_stream_expectations
            WHERE conversation_key=? ORDER BY stream ASC
            """,
            (conversation_key,),
        ).fetchall()
        canonical_rows = conn.execute(
            """
            SELECT stream,stream_sequence,canonical_sequence
            FROM ao_capture_canonical
            WHERE conversation_key=?
            ORDER BY canonical_sequence ASC
            """,
            (conversation_key,),
        ).fetchall()
        observed: Dict[str, List[int]] = {}
        counts: Dict[str, int] = {}
        for row in canonical_rows:
            stream = row["stream"]
            counts[stream] = counts.get(stream, 0) + 1
            if row["stream_sequence"] is not None:
                observed.setdefault(stream, []).append(int(row["stream_sequence"]))

        manifests: List[Dict[str, Any]] = []
        required_complete = True
        for row in expectation_rows:
            stream = row["stream"]
            sequences = sorted(set(observed.get(stream, [])))
            missing = _missing_ranges(
                sequences,
                int(row["expected_first_sequence"]),
                int(row["expected_last_sequence"]),
            )
            allow_empty = bool(row["allow_empty"])
            complete = (allow_empty and not sequences) or (not missing and bool(sequences))
            if bool(row["required"]) and not complete:
                required_complete = False
            manifests.append(
                {
                    "stream": stream,
                    "required": bool(row["required"]),
                    "allow_empty": allow_empty,
                    "expected_first_sequence": int(row["expected_first_sequence"]),
                    "expected_last_sequence": int(row["expected_last_sequence"]),
                    "observed_sequences": sequences,
                    "missing_ranges": missing,
                    "complete": complete,
                }
            )
        return {
            "manifest_declared": bool(expectation_rows),
            "required_streams_complete": bool(expectation_rows) and required_complete,
            "manifests": manifests,
            "observed_counts": counts,
        }

    def _open_findings(self, conversation_key: str) -> List[Dict[str, Any]]:
        rows = self._conn().execute(
            """
            SELECT * FROM ao_capture_findings
            WHERE conversation_key=? AND state='OPEN'
            ORDER BY created_at ASC
            """,
            (conversation_key,),
        ).fetchall()
        return [
            {
                "finding_id": row["finding_id"],
                "finding_type": row["finding_type"],
                "severity": row["severity"],
                "references": json.loads(row["references_json"]),
                "detail": json.loads(row["detail_json"]),
            }
            for row in rows
        ]

    def assess(self, conversation_key: str) -> Dict[str, Any]:
        key = _key(conversation_key, "conversation_key")
        try:
            ledger = self.ledger.verify(key)
        except ConversationNotBound:
            return {
                "conversation_key": key,
                "restore_mode": AlphaOmegaRestoreMode.NO_ALPHA_OMEGA_CAPTURE.value,
                "exact_alpha_omega_complete": False,
                "safe_to_claim_start_to_finish": False,
                "truth_boundary": "NO_BOUND_FFCL_OR_ALPHA_OMEGA_CAPTURE",
            }

        rows = self._conn().execute(
            """
            SELECT * FROM ao_capture_canonical
            WHERE conversation_key=? ORDER BY canonical_sequence ASC
            """,
            (key,),
        ).fetchall()
        canonical_count = len(rows)
        derived_ordering_count = sum(
            row["ordering_authority"]
            == OrderingAuthority.DERIVED_DETERMINISTIC_ORDER.value
            for row in rows
        )
        support_group_counts = [
            len(set(json.loads(row["supporting_groups_json"]))) for row in rows
        ]
        minimum_independent_groups = min(support_group_counts, default=0)
        fully_corroborated = sum(count >= 2 for count in support_group_counts)
        multi_path_complete = canonical_count > 0 and fully_corroborated == canonical_count
        stream = self._stream_assessment(key)
        findings = self._open_findings(key)
        critical_conflict = any(
            item["severity"] == "CRITICAL"
            and item["finding_type"]
            in {
                "MULTIPATH_PAYLOAD_CONFLICT",
                "MULTIPATH_SEQUENCE_CONFLICT",
                "MULTIPATH_STREAM_SEQUENCE_CONFLICT",
                "PATH_REUSE_WITH_DIFFERENT_CONTENT",
                "CANONICAL_SEQUENCE_COLLISION",
            }
            for item in findings
        )
        ledger_tampered = (
            ledger["integrity_state"] == TranscriptIntegrityState.FAIL_HASH_CHAIN.value
        )
        exact = bool(
            ledger.get("exact_context_complete")
            and canonical_count == ledger.get("event_count")
            and not critical_conflict
            and derived_ordering_count == 0
            and stream["required_streams_complete"]
            and multi_path_complete
        )
        if ledger_tampered or critical_conflict:
            mode = AlphaOmegaRestoreMode.REJECT_CONFLICTED
        elif exact:
            mode = AlphaOmegaRestoreMode.EXACT_MULTIPATH_MULTISTREAM_RESTORE
        elif canonical_count and ledger.get("exact_context_complete") and not critical_conflict:
            mode = AlphaOmegaRestoreMode.EXACT_SINGLE_PATH_TRANSCRIPT_RESTORE
        elif canonical_count:
            mode = AlphaOmegaRestoreMode.BOUNDED_MULTIPATH_MULTISTREAM_RESTORE
        else:
            mode = AlphaOmegaRestoreMode.NO_ALPHA_OMEGA_CAPTURE

        pending_rows = self._conn().execute(
            """
            SELECT global_sequence,stream,identity_key,reconciliation_state
            FROM ao_capture_candidates
            WHERE conversation_key=? AND reconciliation_state IN (?,?)
            ORDER BY global_sequence ASC
            """,
            (
                key,
                ReconciliationState.GAP_PENDING.value,
                ReconciliationState.STAGED.value,
            ),
        ).fetchall()
        next_routes: List[str] = []
        if not ledger.get("exact_context_complete"):
            next_routes.append("ACQUIRE_COMPLETE_PRIMARY_TRANSCRIPT_OR_FILL_FFCL_SEQUENCE_GAPS")
        if derived_ordering_count:
            next_routes.append("RECOVER_EXPLICIT_PROVIDER_GLOBAL_SEQUENCE_FOR_DERIVED_EVENTS")
        if not stream["manifest_declared"]:
            next_routes.append("DECLARE_REQUIRED_STREAM_WATERMARKS")
        elif not stream["required_streams_complete"]:
            next_routes.append("FILL_REQUIRED_STREAM_GAPS")
        if canonical_count and not multi_path_complete:
            next_routes.append("CORROBORATE_UNSUPPORTED_EVENTS_THROUGH_AN_INDEPENDENT_CAPTURE_PATH")
        if critical_conflict:
            next_routes.append("RESOLVE_CRITICAL_MULTIPATH_CONFLICT_BEFORE_RESTORE")
        if not self.paths(key):
            next_routes.append("REGISTER_AT_LEAST_ONE_AUTHORISED_CAPTURE_PATH")

        return {
            "conversation_key": key,
            "namespace_key": ledger.get("namespace_key", ""),
            "engine_version": self.VERSION,
            "chatbridge_version": self.CHATBRIDGE_VERSION,
            "architecture_cycle": list(self.ARCHITECTURE_CYCLE),
            "restore_mode": mode.value,
            "exact_alpha_omega_complete": exact,
            "safe_to_claim_start_to_finish": exact,
            "ffcl": ledger,
            "canonical_event_count": canonical_count,
            "derived_ordering_count": derived_ordering_count,
            "multi_path_complete": multi_path_complete,
            "fully_corroborated_event_count": fully_corroborated,
            "minimum_independent_groups_per_event": minimum_independent_groups,
            "stream_assurance": stream,
            "registered_paths": [path.to_dict() for path in self.paths(key)],
            "ranked_failover_plan": self.rank_paths(key),
            "open_findings": findings,
            "pending_candidates": [dict(row) for row in pending_rows],
            "next_acquisition_routes": next_routes,
            "maturity": {
                "source_implementation": "BUILT",
                "deterministic_local": "TEST_REQUIRED_OR_TESTED_BY_CALLER",
                "provider_adapter": "SEPARATE_LIVE_GATE",
                "universal_native_chat_coverage": "NOT_CLAIMED",
            },
            "truth_boundary": (
                "EXACT_START_TO_FINISH_MULTIPATH_MULTISTREAM_CAPTURE_VERIFIED"
                if exact
                else "BOUNDED_OR_SINGLE_PATH_CONTEXT_WITH_EXPLICIT_GAPS_CONFLICTS_AND_ASSURANCE_LIMITS"
            ),
        }

    def finalize(
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
        reconciliation = self.reconcile(
            conversation_key,
            namespace_key,
            allow_derived_ordering=allow_derived_ordering,
        )
        sealed = self.ledger.seal(
            conversation_key,
            expected_last_sequence=expected_last_sequence,
            expected_first_sequence=expected_first_sequence,
            closure_reason=closure_reason,
            terminal_observed=terminal_observed,
        )
        assessment = self.assess(conversation_key)
        return {
            "state": (
                "ALPHA_OMEGA_EXACT_FINALIZED"
                if assessment["exact_alpha_omega_complete"]
                else "ALPHA_OMEGA_BOUNDED_FINALIZED"
            ),
            "reconciliation": reconciliation,
            "ffcl_seal": sealed,
            "assessment": assessment,
        }

