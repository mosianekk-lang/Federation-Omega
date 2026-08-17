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

class AlphaOmegaStageMixin:
    def _registered_path(
        self,
        conversation_key: str,
        path_id: str,
        *,
        require_eligible: bool = True,
    ) -> CapturePath:
        row = self._conn().execute(
            """
            SELECT * FROM ao_capture_paths
            WHERE conversation_key=? AND path_id=?
            """,
            (conversation_key, path_id),
        ).fetchone()
        if not row:
            raise CapturePathNotRegistered(path_id)
        path = self._path_from_row(row)
        if require_eligible and path.state in {
            CapturePathState.FAILED,
            CapturePathState.QUARANTINED,
        }:
            raise CapturePathNotRegistered(
                f"capture path {path_id} is not eligible in state {path.state.value}"
            )
        return path

    def _stage(self, observation: CaptureObservation) -> Dict[str, Any]:
        conversation_key = _key(observation.conversation_key, "conversation_key")
        namespace_key = _namespace(observation.namespace_key)
        path_id = _key(observation.path_id, "path_id")
        path = self._registered_path(conversation_key, path_id)
        if path.conversation_key != conversation_key:
            raise ConversationIdentityConflict("capture path belongs to another conversation")
        if observation.global_sequence is not None and observation.global_sequence < 1:
            raise ValueError("global_sequence must be >= 1")
        if observation.stream_sequence is not None and observation.stream_sequence < 1:
            raise ValueError("stream_sequence must be >= 1")
        if (
            observation.metadata.get("terminal_warning_observed")
            and observation.execution_state == EventExecutionState.EXECUTED_VERIFIED
        ):
            raise TerminalExecutionClaimError(
                "terminal-visible intent cannot be represented as verified execution"
            )

        identity = observation.identity_key()
        payload_hash = observation.payload_hash()
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                """
                SELECT * FROM ao_capture_candidates
                WHERE conversation_key=? AND path_id=? AND identity_key=?
                """,
                (conversation_key, path_id, identity),
            ).fetchone()
            if existing:
                if existing["payload_hash"] == payload_hash:
                    conn.execute("COMMIT")
                    return {
                        "state": "OBSERVATION_REUSED_IDEMPOTENT",
                        "candidate_id": existing["candidate_id"],
                        "identity_key": identity,
                        "payload_hash": payload_hash,
                        "reused": True,
                    }
                conn.execute(
                    """
                    UPDATE ao_capture_candidates
                    SET reconciliation_state=?,updated_at=?
                    WHERE candidate_id=?
                    """,
                    (ReconciliationState.CONFLICTED.value, _now(), existing["candidate_id"]),
                )
                conn.execute("COMMIT")
                self._finding(
                    conversation_key,
                    "PATH_REUSE_WITH_DIFFERENT_CONTENT",
                    severity="CRITICAL",
                    references=[path_id, identity],
                    detail={
                        "existing_payload_hash": existing["payload_hash"],
                        "incoming_payload_hash": payload_hash,
                    },
                )
                raise ObservationConflict(
                    "the same path and source identity produced different content"
                )

            candidate_id = f"ao_candidate_{uuid.uuid4().hex}"
            now = _now()
            conn.execute(
                """
                INSERT INTO ao_capture_candidates VALUES(
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    candidate_id,
                    conversation_key,
                    namespace_key,
                    path_id,
                    observation.stream.value,
                    observation.global_sequence,
                    observation.stream_sequence,
                    identity,
                    payload_hash,
                    _canonical_json(observation.to_dict()),
                    ReconciliationState.STAGED.value,
                    None,
                    now,
                    now,
                ),
            )
            peers = conn.execute(
                """
                SELECT candidate_id,path_id,payload_hash FROM ao_capture_candidates
                WHERE conversation_key=? AND identity_key=?
                """,
                (conversation_key, identity),
            ).fetchall()
            hashes = {row["payload_hash"] for row in peers}
            if len(hashes) > 1:
                conn.execute(
                    """
                    UPDATE ao_capture_candidates
                    SET reconciliation_state=?,updated_at=?
                    WHERE conversation_key=? AND identity_key=?
                    """,
                    (
                        ReconciliationState.CONFLICTED.value,
                        _now(),
                        conversation_key,
                        identity,
                    ),
                )
                self._audit(
                    conn,
                    conversation_key,
                    "OBSERVATION_CONFLICT_QUARANTINED",
                    {
                        "identity_key": identity,
                        "path_ids": [row["path_id"] for row in peers],
                        "payload_hashes": sorted(hashes),
                    },
                )
                conn.execute("COMMIT")
                finding = self._finding(
                    conversation_key,
                    "MULTIPATH_PAYLOAD_CONFLICT",
                    severity="CRITICAL",
                    references=[identity] + [row["path_id"] for row in peers],
                    detail={"payload_hashes": sorted(hashes)},
                )
                return {
                    "state": "OBSERVATION_CONFLICT_QUARANTINED",
                    "candidate_id": candidate_id,
                    "identity_key": identity,
                    "payload_hash": payload_hash,
                    "finding": finding,
                    "reused": False,
                }

            self._audit(
                conn,
                conversation_key,
                "OBSERVATION_STAGED",
                {
                    "candidate_id": candidate_id,
                    "path_id": path_id,
                    "stream": observation.stream.value,
                    "global_sequence": observation.global_sequence,
                    "stream_sequence": observation.stream_sequence,
                    "identity_key": identity,
                    "payload_hash": payload_hash,
                },
            )
            verify = conn.execute(
                "SELECT * FROM ao_capture_candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if not verify:
                raise RuntimeError("observation staging readback failed")
            conn.execute("COMMIT")
            return {
                "state": "OBSERVATION_STAGED_VERIFIED",
                "candidate_id": candidate_id,
                "identity_key": identity,
                "payload_hash": payload_hash,
                "reused": False,
            }
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

    def _candidate_groups(self, conversation_key: str) -> Dict[str, List[sqlite3.Row]]:
        rows = self._conn().execute(
            """
            SELECT * FROM ao_capture_candidates
            WHERE conversation_key=?
            ORDER BY created_at ASC,candidate_id ASC
            """,
            (conversation_key,),
        ).fetchall()
        grouped: Dict[str, List[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(row["identity_key"], []).append(row)
        return grouped

    def _canonical_row(self, conversation_key: str, identity_key: str) -> Optional[sqlite3.Row]:
        return self._conn().execute(
            """
            SELECT * FROM ao_capture_canonical
            WHERE conversation_key=? AND identity_key=?
            """,
            (conversation_key, identity_key),
        ).fetchone()

