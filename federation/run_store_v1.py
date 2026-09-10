"""Durable run/checkpoint store for FUSE Autonomic Completion Fabric v5.


The implementation uses SQLite WAL + compare-and-swap style version checks.  It
stores mission state, learning events and re-entry queue records.  It is a local
reference implementation; provider deployment is a separate maturity gate.
"""
from __future__ import annotations


from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Mapping


SCHEMA = "FUSE-AUTONOMIC-RUN-STORE-V1"




def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)




def digest(value: Any) -> str:
    return sha256(canonical(value).encode()).hexdigest()




@dataclass(frozen=True, slots=True)
class Checkpoint:
    mission_id: str
    version: int
    state: Mapping[str, Any]
    state_sha256: str
    updated_at: float




class VersionConflict(RuntimeError):
    pass




class RunStore:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, timeout=30.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS mission_state(
              mission_id TEXT PRIMARY KEY,
              version INTEGER NOT NULL,
              state_json TEXT NOT NULL,
              state_sha256 TEXT NOT NULL,
              updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS learning_events(
              event_id TEXT PRIMARY KEY,
              mission_id TEXT NOT NULL,
              event_json TEXT NOT NULL,
              event_sha256 TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reentry_queue(
              reentry_id TEXT PRIMARY KEY,
              mission_id TEXT NOT NULL,
              checkpoint_version INTEGER NOT NULL,
              checkpoint_sha256 TEXT NOT NULL,
              state TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            """
        )
        self.db.commit()


    def close(self) -> None:
        self.db.close()


    def read(self, mission_id: str) -> Checkpoint | None:
        row = self.db.execute(
            "SELECT mission_id,version,state_json,state_sha256,updated_at FROM mission_state WHERE mission_id=?",
            (mission_id,),
        ).fetchone()
        if row is None:
            return None
        state = json.loads(row["state_json"])
        if digest(state) != row["state_sha256"]:
            raise RuntimeError("CHECKPOINT_DIGEST_MISMATCH")
        return Checkpoint(row["mission_id"], row["version"], state, row["state_sha256"], row["updated_at"])


    def put(self, mission_id: str, state: Mapping[str, Any], *, expected_version: int | None) -> Checkpoint:
        now = time.time()
        state_dict = dict(state)
        state_json = canonical(state_dict)
        state_sha = digest(state_dict)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT version FROM mission_state WHERE mission_id=?", (mission_id,)).fetchone()
            current = None if row is None else int(row[0])
            if current != expected_version:
                raise VersionConflict(f"EXPECTED_VERSION:{expected_version}:ACTUAL:{current}")
            new_version = 1 if current is None else current + 1
            if current is None:
                self.db.execute(
                    "INSERT INTO mission_state(mission_id,version,state_json,state_sha256,updated_at) VALUES(?,?,?,?,?)",
                    (mission_id, new_version, state_json, state_sha, now),
                )
            else:
                self.db.execute(
                    "UPDATE mission_state SET version=?,state_json=?,state_sha256=?,updated_at=? WHERE mission_id=? AND version=?",
                    (new_version, state_json, state_sha, now, mission_id, current),
                )
                if self.db.execute("SELECT changes()").fetchone()[0] != 1:
                    raise VersionConflict("CHECKPOINT_CAS_FAILED")
        return Checkpoint(mission_id, new_version, state_dict, state_sha, now)


    def append_learning(self, event_id: str, mission_id: str, payload: Mapping[str, Any]) -> str:
        body = dict(payload)
        event_sha = digest(body)
        with self.db:
            self.db.execute(
                "INSERT INTO learning_events(event_id,mission_id,event_json,event_sha256,created_at) VALUES(?,?,?,?,?)",
                (event_id, mission_id, canonical(body), event_sha, time.time()),
            )
        return event_sha


    def enqueue_reentry(self, mission_id: str, checkpoint: Checkpoint, payload: Mapping[str, Any]) -> str:
        reentry_id = f"REENTRY-{mission_id}-{checkpoint.version}-{checkpoint.state_sha256[:12]}"
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO reentry_queue(reentry_id,mission_id,checkpoint_version,checkpoint_sha256,state,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (reentry_id, mission_id, checkpoint.version, checkpoint.state_sha256, "READY", canonical(dict(payload)), time.time()),
            )
        return reentry_id


    def ready_reentries(self, mission_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM reentry_queue WHERE mission_id=? AND state='READY' ORDER BY created_at,reentry_id", (mission_id,)
        ).fetchall()
        return [dict(r) for r in rows]
