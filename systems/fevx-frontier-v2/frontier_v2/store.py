from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .core import canonical, digest, utc_now

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, recorded_at TEXT NOT NULL, provider TEXT NOT NULL,
  status TEXT NOT NULL, module_count INTEGER NOT NULL, semantic_hash TEXT NOT NULL,
  level INTEGER NOT NULL, external_effect INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS module_results(
  run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, module TEXT NOT NULL,
  result_hash TEXT NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY(run_id, module), FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS workflow_canaries(
  run_id TEXT NOT NULL, workflow_id TEXT NOT NULL, passed INTEGER NOT NULL,
  evidence_hash TEXT NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY(run_id, workflow_id), FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS evolution(
  version TEXT PRIMARY KEY, score REAL NOT NULL, config TEXT NOT NULL,
  promoted_at TEXT NOT NULL, predecessor TEXT
);
CREATE TABLE IF NOT EXISTS events(
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
  payload_hash TEXT NOT NULL, previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL UNIQUE, recorded_at TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def dump_database(path: Path) -> str:
    if not path.exists():
        return ""
    connection = connect(path)
    try:
        return "\n".join(connection.iterdump()) + "\n"
    finally:
        connection.close()


def restore_database(path: Path, sql: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    try:
        if sql.strip():
            connection.executescript(sql)
        connection.executescript(SCHEMA)
        connection.commit()
    finally:
        connection.close()


def append_event(connection: sqlite3.Connection, event_type: str, payload: Any) -> str:
    row = connection.execute("SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
    previous = row[0] if row else "GENESIS"
    payload_hash = digest(payload)
    record = {"event_type": event_type, "payload_hash": payload_hash, "previous_hash": previous, "recorded_at": utc_now()}
    event_hash = digest(record)
    connection.execute(
        "INSERT INTO events(event_type,payload_hash,previous_hash,event_hash,recorded_at) VALUES(?,?,?,?,?)",
        (event_type, payload_hash, previous, event_hash, record["recorded_at"]),
    )
    return event_hash


def save_run(path: Path, result: dict[str, Any], modules: list[dict[str, Any]], canaries: list[dict[str, Any]]) -> str:
    connection = connect(path)
    try:
        with connection:
            connection.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
                (result["run_id"], result["recorded_at"], result["provider"], result["status"],
                 result["module_count"], result["semantic_hash"], result["current_verified_level"], 0),
            )
            for ordinal, item in enumerate(modules, 1):
                payload = canonical(item).decode("utf-8")
                connection.execute(
                    "INSERT INTO module_results VALUES(?,?,?,?,?)",
                    (result["run_id"], ordinal, item["system"], digest(item), payload),
                )
            for item in canaries:
                payload = canonical(item).decode("utf-8")
                connection.execute(
                    "INSERT INTO workflow_canaries VALUES(?,?,?,?,?)",
                    (result["run_id"], item["workflow_id"], int(item["passed"]), digest(item), payload),
                )
            head = append_event(connection, "FRONTIER_RUN_VERIFIED", result)
        return head
    finally:
        connection.close()


def current_evolution(path: Path) -> dict[str, Any]:
    connection = connect(path)
    try:
        row = connection.execute("SELECT version,score,config FROM evolution ORDER BY rowid DESC LIMIT 1").fetchone()
        if not row:
            return {"version": "2.0.0", "score": 0.7, "config": {}}
        import json
        return {"version": row[0], "score": row[1], "config": json.loads(row[2])}
    finally:
        connection.close()


def promote_evolution(path: Path, candidate: dict[str, Any], predecessor: str) -> None:
    import json
    connection = connect(path)
    try:
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO evolution VALUES(?,?,?,?,?)",
                (candidate["version"], candidate["score"], json.dumps(candidate["config"], sort_keys=True), utc_now(), predecessor),
            )
            append_event(connection, "EVOLUTION_PROMOTED", candidate)
    finally:
        connection.close()


def verify_chain(path: Path) -> dict[str, Any]:
    connection = connect(path)
    errors, previous = [], "GENESIS"
    try:
        rows = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
        for row in rows:
            record = {"event_type": row["event_type"], "payload_hash": row["payload_hash"], "previous_hash": row["previous_hash"], "recorded_at": row["recorded_at"]}
            if row["previous_hash"] != previous or digest(record) != row["event_hash"]:
                errors.append(row["sequence"])
            previous = row["event_hash"]
        return {"status": "PASSED" if not errors else "FAILED", "errors": errors, "event_count": len(rows), "head_hash": previous}
    finally:
        connection.close()
