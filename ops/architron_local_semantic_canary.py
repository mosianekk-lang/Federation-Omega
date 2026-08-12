from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ExecutionReceipt:
    schema: str
    execution_state: str
    event_id: str
    execution_id: str
    target_key: str
    target_before: str | None
    target_after: str
    target_readback: str
    attempts: int
    idempotent_replay: bool
    recovered_after_failure: bool
    audit_sha256: str
    truth_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SemanticCanaryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS queue(
                event_id TEXT PRIMARY KEY,
                target_key TEXT NOT NULL,
                target_value TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                failure_once INTEGER NOT NULL DEFAULT 0,
                execution_id TEXT
            );
            CREATE TABLE IF NOT EXISTS target_state(
                target_key TEXT PRIMARY KEY,
                target_value TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS receipts(
                event_id TEXT PRIMARY KEY,
                receipt_json TEXT NOT NULL,
                receipt_sha256 TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def enqueue(self, event_id: str, target_key: str, target_value: str, *, fail_once: bool = False) -> bool:
        before = self.db.total_changes
        self.db.execute(
            "INSERT OR IGNORE INTO queue(event_id,target_key,target_value,state,failure_once) VALUES(?,?,?,?,?)",
            (event_id, target_key, target_value, "QUEUED", 1 if fail_once else 0),
        )
        self.db.commit()
        return self.db.total_changes > before

    def _existing_receipt(self, event_id: str) -> ExecutionReceipt | None:
        row = self.db.execute("SELECT receipt_json FROM receipts WHERE event_id=?", (event_id,)).fetchone()
        return ExecutionReceipt(**json.loads(row["receipt_json"])) if row else None

    def run_one(self, event_id: str, *, readback: Callable[[str], str | None] | None = None) -> ExecutionReceipt:
        existing = self._existing_receipt(event_id)
        if existing:
            return ExecutionReceipt(**{**existing.to_dict(), "idempotent_replay": True})
        row = self.db.execute("SELECT * FROM queue WHERE event_id=?", (event_id,)).fetchone()
        if not row:
            raise KeyError(event_id)
        attempts = int(row["attempts"]) + 1
        execution_id = row["execution_id"] or f"ARCH-{uuid.uuid4().hex[:16]}"
        self.db.execute(
            "UPDATE queue SET attempts=?, execution_id=?, state=? WHERE event_id=?",
            (attempts, execution_id, "RUNNING", event_id),
        )
        self.db.commit()
        if bool(row["failure_once"]) and attempts == 1:
            self.db.execute("UPDATE queue SET state='RETRYABLE_FAILURE' WHERE event_id=?", (event_id,))
            self.db.commit()
            raise RuntimeError("SYNTHETIC_RETRYABLE_FAILURE")
        before_row = self.db.execute(
            "SELECT target_value FROM target_state WHERE target_key=?", (row["target_key"],)
        ).fetchone()
        target_before = before_row["target_value"] if before_row else None
        self.db.execute(
            """
            INSERT INTO target_state(target_key,target_value,version) VALUES(?,?,1)
            ON CONFLICT(target_key) DO UPDATE SET target_value=excluded.target_value, version=target_state.version+1
            """,
            (row["target_key"], row["target_value"]),
        )
        self.db.commit()
        readback_value = (
            readback(row["target_key"])
            if readback
            else self.db.execute(
                "SELECT target_value FROM target_state WHERE target_key=?", (row["target_key"],)
            ).fetchone()["target_value"]
        )
        if readback_value != row["target_value"]:
            self.db.execute("UPDATE queue SET state='SEMANTIC_READBACK_FAILED' WHERE event_id=?", (event_id,))
            self.db.commit()
            raise RuntimeError("SEMANTIC_READBACK_MISMATCH")
        audit_payload = {
            "event_id": event_id,
            "execution_id": execution_id,
            "target_key": row["target_key"],
            "target_before": target_before,
            "target_after": row["target_value"],
            "target_readback": readback_value,
            "attempts": attempts,
        }
        audit_sha = hashlib.sha256(
            json.dumps(audit_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        receipt = ExecutionReceipt(
            schema="ARCHITRON-BRIDGE-LOCAL-SEMANTIC-RECEIPT-V1",
            execution_state="LOCAL_SEMANTIC_VERIFIED",
            event_id=event_id,
            execution_id=execution_id,
            target_key=row["target_key"],
            target_before=target_before,
            target_after=row["target_value"],
            target_readback=readback_value,
            attempts=attempts,
            idempotent_replay=False,
            recovered_after_failure=attempts > 1,
            audit_sha256=audit_sha,
            truth_boundary=(
                "This receipt proves a deterministic local event→queue→worker→target→readback→audit path only. "
                "It does not prove Google Apps Script, Cloud Run, Gmail, Drive or any other provider execution."
            ),
        )
        payload = json.dumps(receipt.to_dict(), sort_keys=True, separators=(",", ":"))
        self.db.execute(
            "INSERT INTO receipts(event_id,receipt_json,receipt_sha256) VALUES(?,?,?)",
            (event_id, payload, hashlib.sha256(payload.encode()).hexdigest()),
        )
        self.db.execute("UPDATE queue SET state='DONE' WHERE event_id=?", (event_id,))
        self.db.commit()
        return receipt

    def target_value(self, target_key: str) -> str | None:
        row = self.db.execute("SELECT target_value FROM target_state WHERE target_key=?", (target_key,)).fetchone()
        return row["target_value"] if row else None
