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

class AlphaOmegaPathsMixin:
    def register_path(self, path: CapturePath) -> Dict[str, Any]:
        conversation_key = _key(path.conversation_key, "conversation_key")
        path_id = _key(path.path_id, "path_id")
        payload = path.to_dict()
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                """
                SELECT * FROM ao_capture_paths
                WHERE conversation_key=? AND path_id=?
                """,
                (conversation_key, path_id),
            ).fetchone()
            if row:
                if (
                    row["path_kind"] != path.kind.value
                    or row["source_provider"] != path.source_provider
                    or row["independent_group"] != path.normalized_group()
                ):
                    raise CapturePathConflict(
                        "path identity is already bound to a different kind, provider or independent group"
                    )
                conn.execute(
                    """
                    UPDATE ao_capture_paths
                    SET state=?,priority=?,proof_strength=?,completeness=?,freshness=?,
                        speed=?,reversibility=?,owner_burden=?,privacy_cost=?,
                        maintenance_cost=?,authoritative=?,metadata_json=?,updated_at=?
                    WHERE conversation_key=? AND path_id=?
                    """,
                    (
                        path.state.value,
                        int(path.priority),
                        float(path.proof_strength),
                        float(path.completeness),
                        float(path.freshness),
                        float(path.speed),
                        float(path.reversibility),
                        float(path.owner_burden),
                        float(path.privacy_cost),
                        float(path.maintenance_cost),
                        int(path.authoritative),
                        _canonical_json(path.metadata),
                        _now(),
                        conversation_key,
                        path_id,
                    ),
                )
                reused = True
            else:
                now = _now()
                conn.execute(
                    """
                    INSERT INTO ao_capture_paths VALUES(
                        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                    """,
                    (
                        conversation_key,
                        path_id,
                        path.kind.value,
                        path.source_provider,
                        path.state.value,
                        int(path.priority),
                        float(path.proof_strength),
                        float(path.completeness),
                        float(path.freshness),
                        float(path.speed),
                        float(path.reversibility),
                        float(path.owner_burden),
                        float(path.privacy_cost),
                        float(path.maintenance_cost),
                        path.normalized_group(),
                        int(path.authoritative),
                        _canonical_json(path.metadata),
                        now,
                        now,
                    ),
                )
                reused = False
            self._audit(
                conn,
                conversation_key,
                "CAPTURE_PATH_REGISTERED",
                {**payload, "reused": reused},
            )
            verify = conn.execute(
                """
                SELECT * FROM ao_capture_paths
                WHERE conversation_key=? AND path_id=?
                """,
                (conversation_key, path_id),
            ).fetchone()
            if not verify:
                raise RuntimeError("capture path readback failed")
            conn.execute("COMMIT")
            return {
                "state": "PATH_REGISTERED_VERIFIED",
                "reused": reused,
                "path": self._path_from_row(verify).to_dict(),
            }
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _path_from_row(self, row: sqlite3.Row) -> CapturePath:
        return CapturePath(
            conversation_key=row["conversation_key"],
            path_id=row["path_id"],
            kind=CapturePathKind(row["path_kind"]),
            source_provider=row["source_provider"],
            state=CapturePathState(row["state"]),
            priority=int(row["priority"]),
            proof_strength=float(row["proof_strength"]),
            completeness=float(row["completeness"]),
            freshness=float(row["freshness"]),
            speed=float(row["speed"]),
            reversibility=float(row["reversibility"]),
            owner_burden=float(row["owner_burden"]),
            privacy_cost=float(row["privacy_cost"]),
            maintenance_cost=float(row["maintenance_cost"]),
            independent_group=row["independent_group"],
            authoritative=bool(row["authoritative"]),
            metadata=json.loads(row["metadata_json"]),
        )

    def paths(self, conversation_key: str) -> List[CapturePath]:
        key = _key(conversation_key, "conversation_key")
        rows = self._conn().execute(
            """
            SELECT * FROM ao_capture_paths
            WHERE conversation_key=?
            ORDER BY priority DESC,path_id ASC
            """,
            (key,),
        ).fetchall()
        return [self._path_from_row(row) for row in rows]

    def rank_paths(self, conversation_key: str) -> List[Dict[str, Any]]:
        paths = self.paths(conversation_key)
        route_to_path = {path.path_id: path for path in paths}
        ranked = self.formation.rank([path.route() for path in paths])
        return [
            {
                **route_to_path[route.route_id].to_dict(),
                "formation_score": round(self.formation.score(route), 6),
                "eligible": route_to_path[route.route_id].state
                in {CapturePathState.AVAILABLE, CapturePathState.DEGRADED},
            }
            for route in ranked
        ]

    def set_path_state(
        self,
        conversation_key: str,
        path_id: str,
        state: CapturePathState,
        *,
        reason: str = "",
    ) -> Dict[str, Any]:
        key = _key(conversation_key, "conversation_key")
        path = _key(path_id, "path_id")
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM ao_capture_paths WHERE conversation_key=? AND path_id=?",
                (key, path),
            ).fetchone()
            if not row:
                raise CapturePathNotRegistered(path)
            metadata = json.loads(row["metadata_json"])
            if reason:
                metadata.setdefault("state_transitions", []).append(
                    {"state": state.value, "reason": reason, "at": _now()}
                )
            conn.execute(
                """
                UPDATE ao_capture_paths SET state=?,metadata_json=?,updated_at=?
                WHERE conversation_key=? AND path_id=?
                """,
                (state.value, _canonical_json(metadata), _now(), key, path),
            )
            self._audit(
                conn,
                key,
                "CAPTURE_PATH_STATE_CHANGED",
                {"path_id": path, "state": state.value, "reason": reason},
            )
            conn.execute("COMMIT")
            return {
                "conversation_key": key,
                "path_id": path,
                "state": state.value,
                "failover_plan": self.rank_paths(key),
            }
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def declare_stream_expectations(
        self,
        conversation_key: str,
        expectations: Iterable[StreamExpectation],
    ) -> Dict[str, Any]:
        key = _key(conversation_key, "conversation_key")
        items = list(expectations)
        if not items:
            raise StreamManifestError("at least one stream expectation is required")
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            now = _now()
            for item in items:
                row = conn.execute(
                    """
                    SELECT * FROM ao_stream_expectations
                    WHERE conversation_key=? AND stream=?
                    """,
                    (key, item.stream.value),
                ).fetchone()
                if row and (
                    int(row["expected_first_sequence"])
                    != item.expected_first_sequence
                    or int(row["expected_last_sequence"])
                    != item.expected_last_sequence
                ):
                    raise StreamManifestError(
                        f"stream {item.stream.value} expectation conflicts with the existing manifest"
                    )
                conn.execute(
                    """
                    INSERT INTO ao_stream_expectations VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(conversation_key,stream) DO UPDATE SET
                        required=excluded.required,
                        allow_empty=excluded.allow_empty,
                        updated_at=excluded.updated_at
                    """,
                    (
                        key,
                        item.stream.value,
                        item.expected_first_sequence,
                        item.expected_last_sequence,
                        int(item.required),
                        int(item.allow_empty),
                        now,
                        now,
                    ),
                )
            self._audit(
                conn,
                key,
                "STREAM_MANIFEST_DECLARED",
                {"expectations": [item.to_dict() for item in items]},
            )
            conn.execute("COMMIT")
            return {
                "state": "STREAM_MANIFEST_VERIFIED",
                "conversation_key": key,
                "expectations": [item.to_dict() for item in items],
            }
        except Exception:
            conn.execute("ROLLBACK")
            raise

