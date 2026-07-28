from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DONE_PREDICATES = (
    "operation_occurred",
    "target_resolved",
    "semantic_success",
    "payload_present",
    "result_stored",
    "source_readback_verified",
    "integrity_verified",
    "independent_observation_verified",
    "delivery_confirmed",
    "audit_complete",
    "no_invalidating_contradiction",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SuperiorLogicRuntime:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT UNIQUE NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              payload_hash TEXT NOT NULL,
              predecessor_hash TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS missions(
              mission_id TEXT PRIMARY KEY,
              owner TEXT NOT NULL,
              instruction TEXT NOT NULL,
              state TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload_json = canonical_json(payload)
        previous = self.db.execute(
            "SELECT payload_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        predecessor_hash = previous["payload_hash"] if previous else None
        envelope = canonical_json(
            {
                "event_type": event_type,
                "payload": payload,
                "predecessor_hash": predecessor_hash,
            }
        )
        payload_hash = sha256_text(envelope)
        event_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO events(event_id,event_type,payload_json,payload_hash,predecessor_hash,created_at) VALUES(?,?,?,?,?,?)",
            (event_id, event_type, payload_json, payload_hash, predecessor_hash, utcnow()),
        )
        self.db.commit()
        return {"event_id": event_id, "payload_hash": payload_hash}

    def create_mission(self, owner: str, instruction: str) -> str:
        mission_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO missions(mission_id,owner,instruction,state,created_at) VALUES(?,?,?,?,?)",
            (mission_id, owner, instruction, "RECEIVED", utcnow()),
        )
        self.db.commit()
        self.append_event("MISSION_CREATED", {"mission_id": mission_id, "owner": owner})
        return mission_id

    def derive_done(self, predicates: dict[str, bool]) -> tuple[bool, list[str]]:
        missing = [name for name in DONE_PREDICATES if not predicates.get(name, False)]
        return (not missing, missing)

    def verify_event_chain(self) -> bool:
        previous = None
        for row in self.db.execute("SELECT * FROM events ORDER BY seq"):
            if row["predecessor_hash"] != previous:
                return False
            envelope = canonical_json(
                {
                    "event_type": row["event_type"],
                    "payload": json.loads(row["payload_json"]),
                    "predecessor_hash": row["predecessor_hash"],
                }
            )
            if sha256_text(envelope) != row["payload_hash"]:
                return False
            previous = row["payload_hash"]
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "event_count": self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "mission_count": self.db.execute("SELECT COUNT(*) FROM missions").fetchone()[0],
            "event_chain_valid": self.verify_event_chain(),
        }
