from __future__ import annotations

import hashlib
import json
import re
import secrets
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


@dataclass(frozen=True)
class ResumeClaim:
    stored: StoredRun
    claim_token: str
    lease_expires_at: int


class DurableRunStore:
    """Encrypted local verification store with replay-safe resume fencing.

    SQLite remains a local verification backend. Production must use the same
    state machine and migrations on PostgreSQL together with a managed KMS
    ``StateProtector``.
    """

    def __init__(self, db_path: str, protector: StateProtector):
        if protector is None:
            raise ValueError("a managed StateProtector is required")
        self.protector = protector
        self.conn = sqlite3.connect(db_path, isolation_level=None)
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
              resume_token TEXT,
              resume_lease_until INTEGER,
              updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS durable_agent_approvals (
              mission_id TEXT NOT NULL,
              state_version INTEGER NOT NULL DEFAULT 1,
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
        self._migrate_local_schema()

    def _migrate_local_schema(self) -> None:
        run_columns = {
            row["name"] for row in self.conn.execute(
                "PRAGMA table_info(durable_agent_runs)"
            ).fetchall()
        }
        for name, sql_type in (
            ("resume_token", "TEXT"),
            ("resume_lease_until", "INTEGER"),
        ):
            if name not in run_columns:
                self.conn.execute(
                    f"ALTER TABLE durable_agent_runs ADD COLUMN {name} {sql_type}"
                )
        approval_columns = {
            row["name"] for row in self.conn.execute(
                "PRAGMA table_info(durable_agent_approvals)"
            ).fetchall()
        }
        if "state_version" not in approval_columns:
            self.conn.execute(
                "ALTER TABLE durable_agent_approvals "
                "ADD COLUMN state_version INTEGER NOT NULL DEFAULT 1"
            )

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @staticmethod
    def _aad(mission_id: str, version: int) -> bytes:
        return f"evidenceops-ai-ict:{mission_id}:v{version}".encode()

    @staticmethod
    def _assert_no_obvious_secret(value: str) -> None:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                raise ValueError("serialized run state contains a secret-like value")

    @staticmethod
    def _interruption_ids(raw_json: str) -> set[str]:
        values = json.loads(raw_json)
        ids = {str(item.get("call_id", "")) for item in values}
        ids.discard("")
        return ids

    def _decrypt_row(self, row: sqlite3.Row) -> StoredRun:
        if row["status"] == "COMPLETE":
            raise RuntimeError("completed run state is no longer resumable")
        plaintext = self.protector.decrypt(
            bytes(row["state_ciphertext"]),
            aad=self._aad(row["mission_id"], int(row["state_version"])),
        )
        actual = hashlib.sha256(plaintext).hexdigest()
        if actual != row["state_sha256"]:
            raise RuntimeError("durable run-state digest mismatch")
        return StoredRun(
            mission_id=row["mission_id"],
            status=row["status"],
            state_version=int(row["state_version"]),
            state_json=json.loads(plaintext),
            interruptions=json.loads(row["interruptions_json"]),
            session_id=row["session_id"],
            updated_at=int(row["updated_at"]),
        )

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
        now = int(time.time())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            current = self.conn.execute(
                "SELECT status,state_version,resume_lease_until "
                "FROM durable_agent_runs WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if current and current["status"] == "RESUMING":
                lease = int(current["resume_lease_until"] or 0)
                if lease > now:
                    raise RuntimeError("cannot overwrite an active resume claim")
            version = (int(current["state_version"]) + 1) if current else 1
            plaintext = raw.encode()
            ciphertext = self.protector.encrypt(
                plaintext, aad=self._aad(mission_id, version)
            )
            digest = hashlib.sha256(plaintext).hexdigest()
            self.conn.execute(
                """
                INSERT INTO durable_agent_runs(
                  mission_id,status,state_version,state_ciphertext,state_sha256,
                  protector_key_id,interruptions_json,session_id,resume_token,
                  resume_lease_until,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(mission_id) DO UPDATE SET
                  status=excluded.status,
                  state_version=excluded.state_version,
                  state_ciphertext=excluded.state_ciphertext,
                  state_sha256=excluded.state_sha256,
                  protector_key_id=excluded.protector_key_id,
                  interruptions_json=excluded.interruptions_json,
                  session_id=excluded.session_id,
                  resume_token=NULL,
                  resume_lease_until=NULL,
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
                    None,
                    None,
                    now,
                ),
            )
            self.conn.execute(
                "DELETE FROM durable_agent_approvals WHERE mission_id=?",
                (mission_id,),
            )
            self.conn.execute("COMMIT")
            return version
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def load(self, mission_id: str) -> StoredRun:
        row = self.conn.execute(
            "SELECT * FROM durable_agent_runs WHERE mission_id=?", (mission_id,)
        ).fetchone()
        if row is None:
            raise KeyError(mission_id)
        return self._decrypt_row(row)

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
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT status,state_version,interruptions_json "
                "FROM durable_agent_runs WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if row is None:
                raise KeyError(mission_id)
            if row["status"] != "WAITING_APPROVAL":
                raise RuntimeError("decisions are accepted only while waiting for approval")
            if call_id not in self._interruption_ids(row["interruptions_json"]):
                raise ValueError("decision call_id is not a pending interruption")
            self.conn.execute(
                """
                INSERT INTO durable_agent_approvals(
                  mission_id,state_version,call_id,decision,approver,reason,created_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(mission_id,call_id) DO UPDATE SET
                  state_version=excluded.state_version,
                  decision=excluded.decision,
                  approver=excluded.approver,
                  reason=excluded.reason,
                  created_at=excluded.created_at
                """,
                (
                    mission_id,
                    int(row["state_version"]),
                    call_id,
                    normalized,
                    approver,
                    reason,
                    int(time.time()),
                ),
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def decisions(self, mission_id: str, *, state_version: int | None = None) -> dict[str, str]:
        if state_version is None:
            row = self.conn.execute(
                "SELECT state_version FROM durable_agent_runs WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if row is None:
                raise KeyError(mission_id)
            state_version = int(row["state_version"])
        rows = self.conn.execute(
            "SELECT call_id,decision FROM durable_agent_approvals "
            "WHERE mission_id=? AND state_version=?",
            (mission_id, state_version),
        ).fetchall()
        return {row["call_id"]: row["decision"] for row in rows}

    def claim_for_resume(
        self,
        mission_id: str,
        *,
        expected_state_version: int | None = None,
        lease_seconds: int = 300,
    ) -> ResumeClaim:
        if lease_seconds < 30:
            raise ValueError("resume lease must be at least 30 seconds")
        now = int(time.time())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT * FROM durable_agent_runs WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if row is None:
                raise KeyError(mission_id)
            status = row["status"]
            if status == "RESUMING" and int(row["resume_lease_until"] or 0) <= now:
                self.conn.execute(
                    "UPDATE durable_agent_runs SET status='WAITING_APPROVAL',"
                    "resume_token=NULL,resume_lease_until=NULL,updated_at=? "
                    "WHERE mission_id=?",
                    (now, mission_id),
                )
                row = self.conn.execute(
                    "SELECT * FROM durable_agent_runs WHERE mission_id=?",
                    (mission_id,),
                ).fetchone()
                status = row["status"]
            if status != "WAITING_APPROVAL":
                raise RuntimeError("run is not available for resume")
            version = int(row["state_version"])
            if expected_state_version is not None and version != expected_state_version:
                raise RuntimeError("stale run-state version")
            pending = self._interruption_ids(row["interruptions_json"])
            decisions = self.decisions(mission_id, state_version=version)
            if set(decisions) != pending:
                missing = sorted(pending - set(decisions))
                raise RuntimeError(f"approval coverage incomplete: {missing}")
            token = secrets.token_urlsafe(24)
            lease_until = now + lease_seconds
            updated = self.conn.execute(
                "UPDATE durable_agent_runs SET status='RESUMING',resume_token=?,"
                "resume_lease_until=?,updated_at=? WHERE mission_id=? "
                "AND status='WAITING_APPROVAL' AND state_version=?",
                (token, lease_until, now, mission_id, version),
            )
            if updated.rowcount != 1:
                raise RuntimeError("resume claim race lost")
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        claimed_row = self.conn.execute(
            "SELECT * FROM durable_agent_runs WHERE mission_id=?", (mission_id,)
        ).fetchone()
        return ResumeClaim(
            stored=self._decrypt_row(claimed_row),
            claim_token=token,
            lease_expires_at=lease_until,
        )

    def release_resume(self, mission_id: str, claim_token: str) -> bool:
        now = int(time.time())
        result = self.conn.execute(
            "UPDATE durable_agent_runs SET status='WAITING_APPROVAL',"
            "resume_token=NULL,resume_lease_until=NULL,updated_at=? "
            "WHERE mission_id=? AND status='RESUMING' AND resume_token=?",
            (now, mission_id, claim_token),
        )
        return result.rowcount == 1

    def complete_resume(
        self,
        mission_id: str,
        claim_token: str,
        *,
        expected_state_version: int,
    ) -> None:
        now = int(time.time())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            result = self.conn.execute(
                """
                UPDATE durable_agent_runs SET
                  status='COMPLETE',state_ciphertext=?,state_sha256=?,
                  interruptions_json='[]',session_id=NULL,resume_token=NULL,
                  resume_lease_until=NULL,updated_at=?
                WHERE mission_id=? AND status='RESUMING' AND resume_token=?
                  AND state_version=?
                """,
                (b"", hashlib.sha256(b"").hexdigest(), now, mission_id, claim_token, expected_state_version),
            )
            if result.rowcount != 1:
                raise RuntimeError("stale or invalid resume completion")
            self.conn.execute(
                "DELETE FROM durable_agent_approvals WHERE mission_id=?",
                (mission_id,),
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def re_pause_after_resume(
        self,
        mission_id: str,
        claim_token: str,
        *,
        expected_state_version: int,
        state_json: dict,
        interruptions: list[dict],
        session_id: str | None = None,
    ) -> int:
        raw = json.dumps(state_json, separators=(",", ":"), sort_keys=True)
        self._assert_no_obvious_secret(raw)
        version = expected_state_version + 1
        plaintext = raw.encode()
        ciphertext = self.protector.encrypt(
            plaintext, aad=self._aad(mission_id, version)
        )
        digest = hashlib.sha256(plaintext).hexdigest()
        now = int(time.time())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            result = self.conn.execute(
                """
                UPDATE durable_agent_runs SET
                  status='WAITING_APPROVAL',state_version=?,state_ciphertext=?,
                  state_sha256=?,protector_key_id=?,interruptions_json=?,
                  session_id=?,resume_token=NULL,resume_lease_until=NULL,updated_at=?
                WHERE mission_id=? AND status='RESUMING' AND resume_token=?
                  AND state_version=?
                """,
                (
                    version,
                    ciphertext,
                    digest,
                    self.protector.key_id,
                    json.dumps(interruptions, separators=(",", ":")),
                    session_id,
                    now,
                    mission_id,
                    claim_token,
                    expected_state_version,
                ),
            )
            if result.rowcount != 1:
                raise RuntimeError("stale or invalid resume re-pause")
            self.conn.execute(
                "DELETE FROM durable_agent_approvals WHERE mission_id=?",
                (mission_id,),
            )
            self.conn.execute("COMMIT")
            return version
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def recover_expired_resume_claims(self) -> int:
        now = int(time.time())
        result = self.conn.execute(
            "UPDATE durable_agent_runs SET status='WAITING_APPROVAL',"
            "resume_token=NULL,resume_lease_until=NULL,updated_at=? "
            "WHERE status='RESUMING' AND resume_lease_until<=?",
            (now, now),
        )
        return result.rowcount
