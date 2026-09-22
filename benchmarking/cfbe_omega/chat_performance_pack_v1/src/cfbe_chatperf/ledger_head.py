"""Fenced O(1) SQLite receipt ledger with idempotent append semantics."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_json, sha256_hex


class LedgerConflict(RuntimeError):
    pass


class FenceRejected(RuntimeError):
    pass


class LedgerHead:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS receipts(
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL,
                  generation INTEGER NOT NULL,
                  slot TEXT NOT NULL,
                  fence INTEGER NOT NULL,
                  prior_hash TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  payload_hash TEXT NOT NULL,
                  receipt_hash TEXT NOT NULL,
                  UNIQUE(task_id,generation,slot)
                );
                CREATE TABLE IF NOT EXISTS heads(
                  task_id TEXT PRIMARY KEY,
                  generation INTEGER NOT NULL,
                  fence INTEGER NOT NULL,
                  sequence INTEGER NOT NULL,
                  receipt_hash TEXT NOT NULL
                );
                """
            )

    def head(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM heads WHERE task_id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def append(
        self,
        *,
        task_id: str,
        generation: int,
        slot: str,
        fence: int,
        payload: Mapping[str, Any],
        expected_head_hash: str | None = None,
    ) -> dict[str, Any]:
        if not task_id or not slot or generation < 1 or fence < 1:
            raise ValueError("task_id, slot, positive generation and positive fence are required")
        payload_json = canonical_json(payload).decode("utf-8")
        payload_hash = sha256_hex(payload)
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            duplicate = db.execute(
                "SELECT * FROM receipts WHERE task_id=? AND generation=? AND slot=?",
                (task_id, generation, slot),
            ).fetchone()
            if duplicate:
                if duplicate["payload_hash"] != payload_hash or duplicate["fence"] != fence:
                    raise LedgerConflict("divergent duplicate receipt")
                db.execute("COMMIT")
                result = dict(duplicate)
                result["idempotent_replay"] = True
                return result
            head = db.execute("SELECT * FROM heads WHERE task_id=?", (task_id,)).fetchone()
            prior_hash = head["receipt_hash"] if head else "GENESIS"
            if head and fence < head["fence"]:
                raise FenceRejected("stale fence")
            if head and generation < head["generation"]:
                raise FenceRejected("stale generation")
            if expected_head_hash is not None and expected_head_hash != prior_hash:
                raise FenceRejected("compare-and-swap head mismatch")
            receipt_hash = sha256_hex(
                {
                    "task_id": task_id,
                    "generation": generation,
                    "slot": slot,
                    "fence": fence,
                    "prior_hash": prior_hash,
                    "payload_hash": payload_hash,
                }
            )
            cur = db.execute(
                "INSERT INTO receipts(task_id,generation,slot,fence,prior_hash,payload_json,payload_hash,receipt_hash) VALUES(?,?,?,?,?,?,?,?)",
                (task_id, generation, slot, fence, prior_hash, payload_json, payload_hash, receipt_hash),
            )
            sequence = cur.lastrowid
            db.execute(
                "INSERT INTO heads(task_id,generation,fence,sequence,receipt_hash) VALUES(?,?,?,?,?) "
                "ON CONFLICT(task_id) DO UPDATE SET generation=excluded.generation,fence=excluded.fence,sequence=excluded.sequence,receipt_hash=excluded.receipt_hash",
                (task_id, generation, fence, sequence, receipt_hash),
            )
            db.execute("COMMIT")
            return {
                "sequence": sequence,
                "task_id": task_id,
                "generation": generation,
                "slot": slot,
                "fence": fence,
                "prior_hash": prior_hash,
                "payload_json": payload_json,
                "payload_hash": payload_hash,
                "receipt_hash": receipt_hash,
                "idempotent_replay": False,
            }
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def verify_chain(self, task_id: str) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM receipts WHERE task_id=? ORDER BY sequence", (task_id,)
            ).fetchall()
        prior = "GENESIS"
        issues: list[str] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if row["payload_hash"] != sha256_hex(payload):
                issues.append(f"PAYLOAD_HASH:{row['sequence']}")
            expected = sha256_hex(
                {
                    "task_id": row["task_id"],
                    "generation": row["generation"],
                    "slot": row["slot"],
                    "fence": row["fence"],
                    "prior_hash": prior,
                    "payload_hash": row["payload_hash"],
                }
            )
            if row["prior_hash"] != prior or row["receipt_hash"] != expected:
                issues.append(f"CHAIN:{row['sequence']}")
            prior = row["receipt_hash"]
        return {"decision": "VERIFIED" if not issues else "REJECTED", "count": len(rows), "issues": issues, "head_hash": prior}
