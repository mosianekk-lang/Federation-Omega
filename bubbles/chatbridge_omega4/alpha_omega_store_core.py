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
from .full_fidelity_ledger import FullFidelityConversationLedger, IncompleteTranscript, TranscriptIntegrityState
from .alpha_omega_models import (
    AlphaOmegaRestoreMode, CaptureObservation, CapturePath, CapturePathConflict,
    CapturePathKind, CapturePathNotRegistered, CapturePathState, ConversationStream,
    ObservationConflict, OrderingAuthority, ReconciliationState, ReplayChunk,
    StreamExpectation, StreamManifestError, _canonical_json, _digest, _key,
    _missing_ranges, _namespace, _now,
)

class AlphaOmegaStoreCoreMixin:
    def __init__(
        self,
        path: str,
        ledger: FullFidelityConversationLedger,
        *,
        formation: Optional[FormationEngine] = None,
    ) -> None:
        self.path = path
        self.ledger = ledger
        self.formation = formation or FormationEngine()
        self._local = threading.local()
        self._capture_lock = threading.RLock()
        self._bootstrap()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.path,
                timeout=30,
                isolation_level=None,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def _bootstrap(self) -> None:
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS ao_capture_paths(
                conversation_key TEXT NOT NULL,
                path_id TEXT NOT NULL,
                path_kind TEXT NOT NULL,
                source_provider TEXT NOT NULL,
                state TEXT NOT NULL,
                priority INTEGER NOT NULL,
                proof_strength REAL NOT NULL,
                completeness REAL NOT NULL,
                freshness REAL NOT NULL,
                speed REAL NOT NULL,
                reversibility REAL NOT NULL,
                owner_burden REAL NOT NULL,
                privacy_cost REAL NOT NULL,
                maintenance_cost REAL NOT NULL,
                independent_group TEXT NOT NULL,
                authoritative INTEGER NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY(conversation_key,path_id)
            );

            CREATE TABLE IF NOT EXISTS ao_capture_candidates(
                candidate_id TEXT PRIMARY KEY,
                conversation_key TEXT NOT NULL,
                namespace_key TEXT NOT NULL,
                path_id TEXT NOT NULL,
                stream TEXT NOT NULL,
                global_sequence INTEGER,
                stream_sequence INTEGER,
                identity_key TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                observation_json TEXT NOT NULL,
                reconciliation_state TEXT NOT NULL,
                canonical_sequence INTEGER,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                UNIQUE(conversation_key,path_id,identity_key)
            );

            CREATE TABLE IF NOT EXISTS ao_capture_canonical(
                conversation_key TEXT NOT NULL,
                identity_key TEXT NOT NULL,
                canonical_sequence INTEGER NOT NULL,
                stream TEXT NOT NULL,
                stream_sequence INTEGER,
                payload_hash TEXT NOT NULL,
                chosen_path_id TEXT NOT NULL,
                supporting_paths_json TEXT NOT NULL,
                supporting_groups_json TEXT NOT NULL,
                ordering_authority TEXT NOT NULL,
                event_hash TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY(conversation_key,identity_key),
                UNIQUE(conversation_key,canonical_sequence)
            );

            CREATE TABLE IF NOT EXISTS ao_stream_expectations(
                conversation_key TEXT NOT NULL,
                stream TEXT NOT NULL,
                expected_first_sequence INTEGER NOT NULL,
                expected_last_sequence INTEGER NOT NULL,
                required INTEGER NOT NULL,
                allow_empty INTEGER NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY(conversation_key,stream)
            );

            CREATE TABLE IF NOT EXISTS ao_capture_findings(
                finding_id TEXT PRIMARY KEY,
                finding_key TEXT NOT NULL UNIQUE,
                conversation_key TEXT NOT NULL,
                finding_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                state TEXT NOT NULL,
                references_json TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                resolved_at REAL
            );

            CREATE TABLE IF NOT EXISTS ao_capture_audit(
                audit_id TEXT PRIMARY KEY,
                conversation_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ao_candidates_identity
                ON ao_capture_candidates(conversation_key,identity_key);
            CREATE INDEX IF NOT EXISTS idx_ao_candidates_state
                ON ao_capture_candidates(conversation_key,reconciliation_state);
            CREATE INDEX IF NOT EXISTS idx_ao_canonical_sequence
                ON ao_capture_canonical(conversation_key,canonical_sequence);
            """
        )
        conn.close()

    def _audit(
        self,
        conn: sqlite3.Connection,
        conversation_key: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        conn.execute(
            "INSERT INTO ao_capture_audit VALUES(?,?,?,?,?)",
            (
                f"ao_audit_{uuid.uuid4().hex}",
                conversation_key,
                event_type,
                _canonical_json(payload),
                _now(),
            ),
        )

