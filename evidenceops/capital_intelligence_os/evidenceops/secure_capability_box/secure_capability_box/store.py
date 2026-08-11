from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .audit import audit_hash, canonical_json, redact, verify_chain
from .errors import OperationConflict, ReplayDetected, RevokedHandle
from .models import CapabilityClaims, ExecutionReceipt


class SecureBoxStore:
    """Metadata-only SQLite store. Secret values never enter this boundary."""

    def __init__(self, path: str | Path, *, clock=time.time) -> None:
        self.path = str(path)
        self.clock = clock
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS grants (
              token_id TEXT PRIMARY KEY,
              claims_json TEXT NOT NULL,
              expires_at INTEGER NOT NULL,
              revoked_at INTEGER,
              consumed_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS operations (
              operation_id TEXT PRIMARY KEY,
              request_digest TEXT NOT NULL,
              receipt_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT,
              event_json TEXT NOT NULL,
              previous_hash TEXT NOT NULL,
              event_hash TEXT NOT NULL
            );
            """
        )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def register(self, claims: CapabilityClaims) -> int:
        with self._transaction():
            self.conn.execute(
                "INSERT INTO grants(token_id,claims_json,expires_at) VALUES(?,?,?)",
                (claims.token_id, canonical_json(claims.as_dict()), claims.expires_at),
            )
            return self._append_audit_locked({
                "type": "HANDLE_ISSUED",
                "token_id": claims.token_id,
                "operation_id": claims.operation_id,
                "mission_id": claims.mission_id,
                "connector": claims.connector,
                "action": claims.action,
                "expires_at": claims.expires_at,
            })

    def revoke(self, token_id: str, reason: str) -> int:
        now = int(self.clock())
        with self._transaction():
            changed = self.conn.execute(
                "UPDATE grants SET revoked_at=? WHERE token_id=? AND revoked_at IS NULL",
                (now, token_id),
            ).rowcount
            if changed != 1:
                raise RevokedHandle("capability handle is unknown or already revoked")
            return self._append_audit_locked({"type": "HANDLE_REVOKED", "token_id": token_id, "reason": reason})

    def reserve(self, claims: CapabilityClaims, request_digest: str) -> ExecutionReceipt | None:
        now = int(self.clock())
        with self._transaction():
            row = self.conn.execute(
                "SELECT expires_at,revoked_at,consumed_at FROM grants WHERE token_id=?",
                (claims.token_id,),
            ).fetchone()
            if row is None:
                raise RevokedHandle("capability handle is not registered")
            if row["revoked_at"] is not None:
                raise RevokedHandle("capability handle is revoked")
            if int(row["expires_at"]) <= now:
                raise RevokedHandle("capability handle is expired")
            if row["consumed_at"] is not None:
                raise ReplayDetected("capability handle was already consumed")

            prior = self.conn.execute(
                "SELECT request_digest,receipt_json FROM operations WHERE operation_id=?",
                (claims.operation_id,),
            ).fetchone()
            if prior is not None:
                if prior["request_digest"] != request_digest:
                    raise OperationConflict("operation_id was already used for different input")
                changed = self.conn.execute(
                    "UPDATE grants SET consumed_at=? WHERE token_id=? AND consumed_at IS NULL",
                    (now, claims.token_id),
                ).rowcount
                if changed != 1:
                    raise ReplayDetected("capability handle was consumed concurrently")
                self._append_audit_locked({
                    "type": "IDEMPOTENT_RECEIPT_REPLAY",
                    "token_id": claims.token_id,
                    "operation_id": claims.operation_id,
                })
                receipt = ExecutionReceipt(**json.loads(prior["receipt_json"]))
                return ExecutionReceipt(**{**receipt.as_dict(), "replayed": True})
            changed = self.conn.execute(
                "UPDATE grants SET consumed_at=? WHERE token_id=? AND consumed_at IS NULL",
                (now, claims.token_id),
            ).rowcount
            if changed != 1:
                raise ReplayDetected("capability handle was consumed concurrently")
            self._append_audit_locked({
                "type": "EXECUTION_RESERVED",
                "token_id": claims.token_id,
                "operation_id": claims.operation_id,
            })
            return None

    def complete(self, receipt: ExecutionReceipt, request_digest: str) -> ExecutionReceipt:
        with self._transaction():
            sequence = self._append_audit_locked({
                "type": "EXECUTION_COMPLETED",
                "token_id": receipt.token_id,
                "operation_id": receipt.operation_id,
                "state": receipt.state,
                "result_digest": receipt.result_digest,
            })
            completed = ExecutionReceipt(**{**receipt.as_dict(), "audit_sequence": sequence})
            self.conn.execute(
                "INSERT INTO operations(operation_id,request_digest,receipt_json) VALUES(?,?,?)",
                (completed.operation_id, request_digest, canonical_json(completed.as_dict())),
            )
            return completed

    def fail(self, claims: CapabilityClaims, failure_class: str) -> int:
        with self._transaction():
            return self._append_audit_locked({
                "type": "EXECUTION_FAILED",
                "token_id": claims.token_id,
                "operation_id": claims.operation_id,
                "failure_class": failure_class,
            })

    def audit_rows(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT sequence,event_json,previous_hash,event_hash FROM audit_events ORDER BY sequence"
        ).fetchall()
        return [dict(row) for row in rows]

    def incomplete_operations(self) -> list[dict[str, Any]]:
        """Return consumed grants without a final receipt for reconciliation."""
        rows = self.conn.execute(
            """
            SELECT g.token_id,g.claims_json,g.consumed_at
              FROM grants g
             WHERE g.consumed_at IS NOT NULL
               AND NOT EXISTS (
                 SELECT 1 FROM operations o
                  WHERE o.operation_id=json_extract(g.claims_json,'$.operation_id')
               )
             ORDER BY g.consumed_at,g.token_id
            """
        ).fetchall()
        return [
            {
                "token_id": row["token_id"],
                "operation_id": json.loads(row["claims_json"])["operation_id"],
                "consumed_at": int(row["consumed_at"]),
            }
            for row in rows
        ]

    def verify_audit(self) -> bool:
        verify_chain(self.audit_rows())
        return True

    def snapshot(self) -> dict[str, Any]:
        """Export recoverable control metadata; never exports provider payloads."""
        with self._lock:
            payload = {
                "schema": "SCB-METADATA-1",
                "grants": [dict(row) for row in self.conn.execute(
                    "SELECT token_id,claims_json,expires_at,revoked_at,consumed_at FROM grants ORDER BY token_id"
                )],
                "operations": [dict(row) for row in self.conn.execute(
                    "SELECT operation_id,request_digest,receipt_json FROM operations ORDER BY operation_id"
                )],
                "audit_events": self.audit_rows(),
            }
            verify_chain(payload["audit_events"])
            return payload

    @classmethod
    def restore(cls, path: str | Path, snapshot: dict[str, Any], *, clock=time.time) -> "SecureBoxStore":
        if snapshot.get("schema") != "SCB-METADATA-1":
            raise ValueError("unsupported snapshot schema")
        verify_chain(snapshot.get("audit_events", []))
        store = cls(path, clock=clock)
        with store._transaction():
            if any(store.conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in ("grants", "operations", "audit_events")):
                raise ValueError("restore target must be empty")
            store.conn.executemany(
                "INSERT INTO grants(token_id,claims_json,expires_at,revoked_at,consumed_at) VALUES(:token_id,:claims_json,:expires_at,:revoked_at,:consumed_at)",
                snapshot.get("grants", []),
            )
            store.conn.executemany(
                "INSERT INTO operations(operation_id,request_digest,receipt_json) VALUES(:operation_id,:request_digest,:receipt_json)",
                snapshot.get("operations", []),
            )
            store.conn.executemany(
                "INSERT INTO audit_events(sequence,event_json,previous_hash,event_hash) VALUES(:sequence,:event_json,:previous_hash,:event_hash)",
                snapshot.get("audit_events", []),
            )
        store.verify_audit()
        return store

    def health(self) -> dict[str, Any]:
        self.conn.execute("SELECT 1").fetchone()
        return {"state": "HEALTHY", "audit_valid": self.verify_audit()}

    def _append_audit_locked(self, event: dict[str, Any]) -> int:
        redacted = redact(event)
        previous = self.conn.execute(
            "SELECT event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else "0" * 64
        next_sequence = int(self.conn.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 AS value FROM audit_events"
        ).fetchone()["value"])
        event_hash = audit_hash(next_sequence, redacted, previous_hash)
        self.conn.execute(
            "INSERT INTO audit_events(sequence,event_json,previous_hash,event_hash) VALUES(?,?,?,?)",
            (next_sequence, canonical_json(redacted), previous_hash, event_hash),
        )
        return next_sequence

    class _Transaction:
        def __init__(self, owner: "SecureBoxStore") -> None:
            self.owner = owner

        def __enter__(self):
            self.owner._lock.acquire()
            self.owner.conn.execute("BEGIN IMMEDIATE")

        def __exit__(self, exc_type, exc, tb):
            try:
                self.owner.conn.execute("ROLLBACK" if exc_type else "COMMIT")
            finally:
                self.owner._lock.release()

    def _transaction(self) -> "SecureBoxStore._Transaction":
        return self._Transaction(self)
