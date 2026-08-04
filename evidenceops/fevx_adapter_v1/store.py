from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .core import digest, utc_now

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS recommendations(
    recommendation_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    matter_id TEXT NOT NULL,
    case_wall_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proofs(
    proof_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL UNIQUE,
    proof_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(recommendation_id)
);
CREATE TABLE IF NOT EXISTS ledger(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoints(
    checkpoint_id TEXT PRIMARY KEY,
    ledger_head_hash TEXT NOT NULL,
    database_semantic_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class DerivedStore:
    """Persistence for derived advisory records only.

    The schema intentionally contains no source, document, fact, verified-fact,
    chronology or original-evidence table.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA_SQL)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def table_names(self) -> set[str]:
        return {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            if not row[0].startswith("sqlite_")
        }

    def get_by_idempotency(self, key: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT payload_json FROM recommendations WHERE idempotency_key=?",
            (key,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def recommendation_count(self) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM recommendations"
            ).fetchone()[0]
        )

    def ledger_count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM ledger").fetchone()[0])

    def _ledger_head(self, connection: sqlite3.Connection | None = None) -> str:
        conn = connection or self.connection
        row = conn.execute(
            "SELECT event_hash FROM ledger ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return str(row[0]) if row else "GENESIS"

    def append_ledger(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        record_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        previous_hash = self._ledger_head(connection)
        created_at = utc_now()
        body = {
            "event_type": event_type,
            "record_id": record_id,
            "previous_hash": previous_hash,
            "payload": payload,
            "created_at": created_at,
        }
        event_hash = digest(body)
        connection.execute(
            """
            INSERT INTO ledger(
                event_type,record_id,previous_hash,event_hash,payload_json,created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                event_type,
                record_id,
                previous_hash,
                event_hash,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                created_at,
            ),
        )
        return {**body, "event_hash": event_hash}

    def verify_ledger(self) -> dict[str, Any]:
        previous = "GENESIS"
        errors: list[str] = []
        count = 0
        for row in self.connection.execute("SELECT * FROM ledger ORDER BY sequence"):
            count += 1
            payload = json.loads(row["payload_json"])
            body = {
                "event_type": row["event_type"],
                "record_id": row["record_id"],
                "previous_hash": row["previous_hash"],
                "payload": payload,
                "created_at": row["created_at"],
            }
            expected = digest(body)
            if row["previous_hash"] != previous:
                errors.append(f"sequence {row['sequence']}: previous hash mismatch")
            if row["event_hash"] != expected:
                errors.append(f"sequence {row['sequence']}: event hash mismatch")
            previous = row["event_hash"]
        return {
            "status": "PASSED" if not errors else "FAILED",
            "event_count": count,
            "ledger_head_hash": previous,
            "errors": errors,
        }

    def verify_records(self) -> dict[str, Any]:
        errors: list[str] = []
        for row in self.connection.execute("SELECT * FROM recommendations"):
            payload = json.loads(row["payload_json"])
            if digest(payload["derived_payload"]) != row["output_hash"]:
                errors.append(
                    f"recommendation {row['recommendation_id']}: output hash mismatch"
                )
        for row in self.connection.execute("SELECT * FROM proofs"):
            payload = json.loads(row["payload_json"])
            proof_body = dict(payload)
            proof_body.pop("proof_hash", None)
            proof_body.pop("ledger_event_hash", None)
            if digest(proof_body) != row["proof_hash"]:
                errors.append(f"proof {row['proof_id']}: proof hash mismatch")
        return {"status": "PASSED" if not errors else "FAILED", "errors": errors}

    def verify_schema_boundary(self) -> dict[str, Any]:
        tables = self.table_names()
        prohibited_fragments = ("source", "document", "fact", "evidence", "chronology")
        prohibited = sorted(
            table
            for table in tables
            if any(fragment in table.lower() for fragment in prohibited_fragments)
        )
        allowed = {"recommendations", "proofs", "ledger", "checkpoints"}
        unexpected = sorted(tables - allowed)
        return {
            "status": "PASSED" if not prohibited and not unexpected else "FAILED",
            "tables": sorted(tables),
            "prohibited_tables": prohibited,
            "unexpected_tables": unexpected,
        }

    def verify_all(self) -> dict[str, Any]:
        ledger = self.verify_ledger()
        records = self.verify_records()
        schema = self.verify_schema_boundary()
        return {
            "status": (
                "PASSED"
                if ledger["status"] == records["status"] == schema["status"] == "PASSED"
                else "FAILED"
            ),
            "ledger": ledger,
            "records": records,
            "schema_boundary": schema,
        }

    def dump_sql(self) -> str:
        return "\n".join(self.connection.iterdump()) + "\n"

    @staticmethod
    def restore_sql(path: str | Path, dump_text: str) -> "DerivedStore":
        target = Path(path)
        for candidate in (
            target,
            Path(str(target) + "-wal"),
            Path(str(target) + "-shm"),
        ):
            candidate.unlink(missing_ok=True)
        connection = sqlite3.connect(target)
        try:
            if dump_text.strip():
                connection.executescript(dump_text)
            connection.commit()
        finally:
            connection.close()
        return DerivedStore(target)

    def database_semantic_hash(self) -> str:
        snapshot: dict[str, Any] = {}
        for table in ("recommendations", "proofs", "ledger", "checkpoints"):
            columns = [
                row[1]
                for row in self.connection.execute(f"PRAGMA table_info({table})")
            ]
            rows = [
                dict(zip(columns, tuple(row)))
                for row in self.connection.execute(
                    f"SELECT * FROM {table} ORDER BY 1"
                )
            ]
            snapshot[table] = rows
        return digest(snapshot)
