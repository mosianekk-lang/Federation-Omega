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

class AlphaOmegaFindingsMixin:
    def _finding(
        self,
        conversation_key: str,
        finding_type: str,
        *,
        severity: str,
        references: Sequence[str],
        detail: Dict[str, Any],
    ) -> Dict[str, Any]:
        key = _digest(
            {
                "conversation_key": conversation_key,
                "finding_type": finding_type,
                "references": sorted(str(item) for item in references),
            }
        )
        conn = self._conn()
        now = _now()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM ao_capture_findings WHERE finding_key=?",
                (key,),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE ao_capture_findings
                    SET severity=?,state='OPEN',detail_json=?,resolved_at=NULL
                    WHERE finding_key=?
                    """,
                    (severity, _canonical_json(detail), key),
                )
                finding_id = row["finding_id"]
            else:
                finding_id = f"ao_find_{uuid.uuid4().hex}"
                conn.execute(
                    "INSERT INTO ao_capture_findings VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        finding_id,
                        key,
                        conversation_key,
                        finding_type,
                        severity,
                        "OPEN",
                        _canonical_json(list(references)),
                        _canonical_json(detail),
                        now,
                        None,
                    ),
                )
            self._audit(
                conn,
                conversation_key,
                "FINDING_OPENED",
                {
                    "finding_id": finding_id,
                    "finding_type": finding_type,
                    "severity": severity,
                    "references": list(references),
                },
            )
            conn.execute("COMMIT")
            return {
                "finding_id": finding_id,
                "finding_key": key,
                "finding_type": finding_type,
                "severity": severity,
                "state": "OPEN",
            }
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def resolve_finding(self, finding_id: str, *, resolution: str) -> Dict[str, Any]:
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                "SELECT * FROM ao_capture_findings WHERE finding_id=?",
                (finding_id,),
            ).fetchone()
            if not row:
                raise KeyError(finding_id)
            detail = json.loads(row["detail_json"])
            detail["resolution"] = resolution
            conn.execute(
                """
                UPDATE ao_capture_findings
                SET state='RESOLVED',detail_json=?,resolved_at=?
                WHERE finding_id=?
                """,
                (_canonical_json(detail), _now(), finding_id),
            )
            self._audit(
                conn,
                row["conversation_key"],
                "FINDING_RESOLVED",
                {"finding_id": finding_id, "resolution": resolution},
            )
            conn.execute("COMMIT")
            return {"finding_id": finding_id, "state": "RESOLVED"}
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _resolve_open_findings_by_type(
        self,
        conversation_key: str,
        finding_type: str,
        *,
        resolution: str,
    ) -> int:
        conn = self._conn()
        conn.execute("BEGIN IMMEDIATE")
        try:
            rows = conn.execute(
                """
                SELECT finding_id,detail_json FROM ao_capture_findings
                WHERE conversation_key=? AND finding_type=? AND state='OPEN'
                """,
                (conversation_key, finding_type),
            ).fetchall()
            for row in rows:
                detail = json.loads(row["detail_json"])
                detail["resolution"] = resolution
                conn.execute(
                    """
                    UPDATE ao_capture_findings
                    SET state='RESOLVED',detail_json=?,resolved_at=?
                    WHERE finding_id=?
                    """,
                    (_canonical_json(detail), _now(), row["finding_id"]),
                )
            if rows:
                self._audit(
                    conn,
                    conversation_key,
                    "FINDINGS_AUTO_RESOLVED",
                    {
                        "finding_type": finding_type,
                        "count": len(rows),
                        "resolution": resolution,
                    },
                )
            conn.execute("COMMIT")
            return len(rows)
        except Exception:
            conn.execute("ROLLBACK")
            raise

