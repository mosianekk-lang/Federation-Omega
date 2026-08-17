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

class AlphaOmegaCanonicalMixin:
    def _choose_path(self, conversation_key: str, path_ids: Sequence[str]) -> CapturePath:
        ranked = self.rank_paths(conversation_key)
        eligible = [item for item in ranked if item["path_id"] in path_ids and item["eligible"]]
        if eligible:
            selected_id = eligible[0]["path_id"]
            return self._registered_path(conversation_key, selected_id)

        # A path can fail after its already-observed payload was staged. Failure blocks
        # new acquisition but does not erase historical evidence. Preserve that payload
        # and mark the failover limitation in the assessment instead of freezing the
        # objective or inventing a replacement.
        historical = [
            item
            for item in ranked
            if item["path_id"] in path_ids
            and item["state"] != CapturePathState.QUARANTINED.value
        ]
        if not historical:
            raise CapturePathNotRegistered(
                "no usable historical or live capture path remains for the observation"
            )
        return self._registered_path(
            conversation_key,
            historical[0]["path_id"],
            require_eligible=False,
        )

    def _update_corroboration(
        self,
        conversation_key: str,
        identity_key: str,
        supporting_paths: Sequence[str],
        supporting_groups: Sequence[str],
    ) -> Dict[str, Any]:
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                """
                SELECT * FROM ao_capture_canonical
                WHERE conversation_key=? AND identity_key=?
                """,
                (conversation_key, identity_key),
            ).fetchone()
            if not row:
                conn.execute("ROLLBACK")
                return {"state": "CANONICAL_NOT_FOUND"}
            merged_paths = sorted(
                set(json.loads(row["supporting_paths_json"])) | set(supporting_paths)
            )
            merged_groups = sorted(
                set(json.loads(row["supporting_groups_json"])) | set(supporting_groups)
            )
            conn.execute(
                """
                UPDATE ao_capture_canonical
                SET supporting_paths_json=?,supporting_groups_json=?,updated_at=?
                WHERE conversation_key=? AND identity_key=?
                """,
                (
                    _canonical_json(merged_paths),
                    _canonical_json(merged_groups),
                    _now(),
                    conversation_key,
                    identity_key,
                ),
            )
            candidate_state = (
                ReconciliationState.CORROBORATED.value
                if len(merged_groups) >= 2
                else ReconciliationState.RECONCILED.value
            )
            conn.execute(
                """
                UPDATE ao_capture_candidates
                SET reconciliation_state=?,canonical_sequence=?,updated_at=?
                WHERE conversation_key=? AND identity_key=?
                """,
                (
                    candidate_state,
                    int(row["canonical_sequence"]),
                    _now(),
                    conversation_key,
                    identity_key,
                ),
            )
            self._audit(
                conn,
                conversation_key,
                "CANONICAL_CORROBORATION_UPDATED",
                {
                    "identity_key": identity_key,
                    "supporting_paths": merged_paths,
                    "supporting_groups": merged_groups,
                },
            )
            conn.execute("COMMIT")
            return {
                "state": "CANONICAL_CORROBORATION_VERIFIED",
                "identity_key": identity_key,
                "canonical_sequence": int(row["canonical_sequence"]),
                "supporting_paths": merged_paths,
                "supporting_groups": merged_groups,
            }
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

    def _append_canonical(
        self,
        observation: CaptureObservation,
        *,
        canonical_sequence: int,
        supporting_paths: Sequence[str],
        supporting_groups: Sequence[str],
        ordering_authority: OrderingAuthority,
        chosen_path_id: str,
    ) -> Dict[str, Any]:
        event = observation.to_event(
            canonical_sequence,
            supporting_paths=supporting_paths,
            supporting_groups=supporting_groups,
            ordering_authority=ordering_authority,
        )
        ledger_receipt = self.ledger.append(event)
        identity_key = observation.identity_key()
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                """
                SELECT * FROM ao_capture_canonical
                WHERE conversation_key=? AND identity_key=?
                """,
                (observation.conversation_key, identity_key),
            ).fetchone()
            if existing:
                if (
                    int(existing["canonical_sequence"]) != canonical_sequence
                    or existing["payload_hash"] != observation.payload_hash()
                ):
                    raise ObservationConflict(
                        "canonical mapping changed after FFCL append"
                    )
            else:
                now = _now()
                conn.execute(
                    """
                    INSERT INTO ao_capture_canonical VALUES(
                        ?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                    """,
                    (
                        observation.conversation_key,
                        identity_key,
                        canonical_sequence,
                        observation.stream.value,
                        observation.stream_sequence,
                        observation.payload_hash(),
                        chosen_path_id,
                        _canonical_json(sorted(set(supporting_paths))),
                        _canonical_json(sorted(set(supporting_groups))),
                        ordering_authority.value,
                        ledger_receipt["event_hash"],
                        now,
                        now,
                    ),
                )
            candidate_state = (
                ReconciliationState.CORROBORATED.value
                if len(set(supporting_groups)) >= 2
                else ReconciliationState.RECONCILED.value
            )
            conn.execute(
                """
                UPDATE ao_capture_candidates
                SET reconciliation_state=?,canonical_sequence=?,updated_at=?
                WHERE conversation_key=? AND identity_key=?
                """,
                (
                    candidate_state,
                    canonical_sequence,
                    _now(),
                    observation.conversation_key,
                    identity_key,
                ),
            )
            self._audit(
                conn,
                observation.conversation_key,
                "CANONICAL_EVENT_APPENDED",
                {
                    "identity_key": identity_key,
                    "canonical_sequence": canonical_sequence,
                    "ordering_authority": ordering_authority.value,
                    "supporting_paths": sorted(set(supporting_paths)),
                    "supporting_groups": sorted(set(supporting_groups)),
                    "event_hash": ledger_receipt["event_hash"],
                },
            )
            conn.execute("COMMIT")
            return {
                "state": "CANONICAL_EVENT_APPENDED_VERIFIED",
                "identity_key": identity_key,
                "canonical_sequence": canonical_sequence,
                "ordering_authority": ordering_authority.value,
                "supporting_paths": sorted(set(supporting_paths)),
                "supporting_groups": sorted(set(supporting_groups)),
                "ledger_receipt": ledger_receipt,
            }
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

