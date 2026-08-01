from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Protocol

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"(?i)(api[_-]?key|password|client[_-]?secret)\s*[:=]\s*[^\s,;]{6,}"),
)


class StateProtector(Protocol):
    """KMS/envelope-protection boundary for serialized SDK state."""

    key_id: str

    def encrypt(self, plaintext: bytes, *, aad: bytes) -> bytes: ...

    def decrypt(self, ciphertext: bytes, *, aad: bytes) -> bytes: ...


@dataclass(frozen=True)
class StoredRun:
    mission_id: str
    status: str
    state_version: int
    state_json: dict
    interruptions: list[dict]
    session_id: str | None
    updated_at: int


class DurableRunStore:
    """Persists paused agent runs without ever storing plaintext run state.

    SQLite is used for local verification. Production uses the same schema in
    PostgreSQL and a managed KMS-backed StateProtector.
    """

    def __init__(self, db_path: str, protector: StateProtector):
        if protector is None:
            raise ValueError("a managed StateProtector is required")
        self.protector = protector
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS durable_agent_runs (
              mission_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              state_version INTEGER NOT NULL,
              state_ciphertext BLOB NOT NULL,
              state_sha256 TEXT NOT NULL,
              protector_key_id TEXT NOT NULL,
              interruptions_json TEXT NOT NULL,
              session_id TEXT,
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS durable_agent_approvals (
              mission_id TEXT NOT NULL,
              call_id TEXT NOT NULL,
              decision TEXT NOT NULL CHECK(decision IN ('APPROVE','REJECT')),
              approver TEXT NOT NULL,
              reason TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              PRIMARY KEY(mission_id, call_id),
              FOREIGN KEY(mission_id) REFERENCES durable_agent_runs(mission_id)
            );
            """
        )
        self.conn.commit()

    @staticmethod
    def _aad(mission_id: str, version: int) -> bytes:
        return f"evidenceops-ai-ict:{mission_id}:v{version}".encode()

    @staticmethod
    def _assert_no_obvious_secret(value: str) -> None:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                raise ValueError("serialized run state contains a secret-like value")

    def save_paused(
        self,
        mission_id: str,
        state_json: dict,
        interruptions: list[dict],
        *,
        session_id: str | None = None,
    ) -> int:
        raw = json.dumps(state_json, separators=(",", ":"), sort_keys=True)
        self._assert_no_obvious_secret(raw)
        current = self.conn.execute(
            "SELECT state_version FROM durable_agent_runs WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        version = (int(current[0]) + 1) if current else 1
        plaintext = raw.encode()
        ciphertext = self.protector.encrypt(
            plaintext, aad=self._aad(mission_id, version)
        )
        digest = hashlib.sha256(plaintext).hexdigest()
        now = int(time.time())
        self.conn.execute(
            """
            INSERT INTO durable_agent_runs(
              mission_id,status,state_version,state_ciphertext,state_sha256,
              protector_key_id,interruptions_json,session_id,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(mission_id) DO UPDATE SET
              status=excluded.status,
              state_version=excluded.state_version,
              state_ciphertext=excluded.state_ciphertext,
              state_sha256=excluded.state_sha256,
              protector_key_id=excluded.protector_key_id,
              interruptions_json=excluded.interruptions_json,
              session_id=excluded.session_id,
              updated_at=excluded.updated_at
            """,
            (
                mission_id,
                "WAITING_APPROVAL",
                version,
                ciphertext,
                digest,
                self.protector.key_id,
                json.dumps(interruptions, separators=(",", ":")),
                session_id,
                now,
            ),
        )
        self.conn.commit()
        return version

    def load(self, mission_id: str) -> StoredRun:
        row = self.conn.execute(
            "SELECT * FROM durable_agent_runs WHERE mission_id=?", (mission_id,)
        ).fetchone()
        if row is None:
            raise KeyError(mission_id)
        plaintext = self.protector.decrypt(
            bytes(row["state_ciphertext"]),
            aad=self._aad(mission_id, int(row["state_version"])),
        )
        actual = hashlib.sha256(plaintext).hexdigest()
        if actual != row["state_sha256"]:
            raise RuntimeError("durable run-state digest mismatch")
        return StoredRun(
            mission_id=mission_id,
            status=row["status"],
            state_version=int(row["state_version"]),
            state_json=json.loads(plaintext),
            interruptions=json.loads(row["interruptions_json"]),
            session_id=row["session_id"],
            updated_at=int(row["updated_at"]),
        )

    def record_decision(
        self,
        mission_id: str,
        call_id: str,
        decision: str,
        approver: str,
        reason: str,
    ) -> None:
        normalized = decision.upper()
        if normalized not in {"APPROVE", "REJECT"}:
            raise ValueError("decision must be APPROVE or REJECT")
        self.conn.execute(
            """
            INSERT INTO durable_agent_approvals(
              mission_id,call_id,decision,approver,reason,created_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(mission_id,call_id) DO UPDATE SET
              decision=excluded.decision,
              approver=excluded.approver,
              reason=excluded.reason,
              created_at=excluded.created_at
            """,
            (mission_id, call_id, normalized, approver, reason, int(time.time())),
        )
        self.conn.commit()

    def decisions(self, mission_id: str) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT call_id,decision FROM durable_agent_approvals WHERE mission_id=?",
            (mission_id,),
        ).fetchall()
        return {row["call_id"]: row["decision"] for row in rows}
