from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .hashing import canonical_json, sha256_value
from .models import Event


class EventStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def connection(self):
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                '''
                CREATE TABLE IF NOT EXISTS federation_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_event_hash TEXT,
                    event_hash TEXT NOT NULL UNIQUE,
                    body_hash TEXT NOT NULL,
                    inserted_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_entity_sequence
                    ON federation_events(entity_id, sequence);
                CREATE TABLE IF NOT EXISTS mission_contracts (
                    mission_id TEXT PRIMARY KEY,
                    contract_json TEXT NOT NULL,
                    contract_sha256 TEXT NOT NULL UNIQUE,
                    inserted_at TEXT NOT NULL
                );
                '''
            )

    def append(self, event: Event) -> dict[str, Any]:
        body = event.body()
        body_hash = event.body_hash()
        inserted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT body_hash, event_hash, sequence FROM federation_events WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
            if existing:
                if existing["body_hash"] != body_hash:
                    raise ValueError("event_id conflict")
                return {
                    "state": "IDEMPOTENT_REPLAY",
                    "sequence": existing["sequence"],
                    "event_hash": existing["event_hash"],
                }

            previous = connection.execute(
                "SELECT event_hash FROM federation_events WHERE entity_id=? ORDER BY sequence DESC LIMIT 1",
                (event.entity_id,),
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else None
            envelope = {
                "body": body,
                "body_hash": body_hash,
                "previous_event_hash": previous_hash,
            }
            event_hash = sha256_value(envelope)
            cursor = connection.execute(
                '''
                INSERT INTO federation_events(
                    event_id, entity_id, event_type, occurred_at, observed_at,
                    source, authority, payload_json, previous_event_hash,
                    event_hash, body_hash, inserted_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ''',
                (
                    event.event_id,
                    event.entity_id,
                    event.event_type,
                    event.occurred_at,
                    event.observed_at,
                    event.source,
                    event.authority,
                    canonical_json(event.payload),
                    previous_hash,
                    event_hash,
                    body_hash,
                    inserted_at,
                ),
            )
            return {
                "state": "APPENDED",
                "sequence": cursor.lastrowid,
                "event_hash": event_hash,
                "previous_event_hash": previous_hash,
            }

    def events(self, entity_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM federation_events"
        params: tuple[Any, ...] = ()
        if entity_id is not None:
            query += " WHERE entity_id=?"
            params = (entity_id,)
        query += " ORDER BY sequence"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def verify(self) -> dict[str, Any]:
        with self.connection() as connection:
            quick = connection.execute("PRAGMA quick_check").fetchone()[0]
            entities = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT entity_id FROM federation_events ORDER BY entity_id"
                )
            ]
        checked = 0
        for entity_id in entities:
            previous_hash = None
            for row in self.events(entity_id):
                body = {
                    "event_id": row["event_id"],
                    "entity_id": row["entity_id"],
                    "event_type": row["event_type"],
                    "occurred_at": row["occurred_at"],
                    "observed_at": row["observed_at"],
                    "source": row["source"],
                    "authority": row["authority"],
                    "payload": row["payload"],
                }
                body_hash = sha256_value(body)
                expected = sha256_value(
                    {
                        "body": body,
                        "body_hash": body_hash,
                        "previous_event_hash": previous_hash,
                    }
                )
                if body_hash != row["body_hash"] or expected != row["event_hash"]:
                    raise ValueError(f"hash-chain mismatch for {row['event_id']}")
                if row["previous_event_hash"] != previous_hash:
                    raise ValueError(f"previous hash mismatch for {row['event_id']}")
                previous_hash = row["event_hash"]
                checked += 1
        return {"quick_check": quick, "event_count": checked, "entity_count": len(entities)}

    def project(self, entity_id: str) -> dict[str, Any]:
        state: dict[str, Any] = {}
        last_event: dict[str, Any] | None = None
        superseded_by: str | None = None
        events = self.events(entity_id)
        for event in events:
            payload = event["payload"]
            if event["event_type"] == "STATE_SET":
                state = dict(payload["state"])
            elif event["event_type"] == "STATE_PATCH":
                state.update(payload["patch"])
            elif event["event_type"] == "STATUS_SET":
                state["status"] = payload["status"]
            elif event["event_type"] == "SUPERSEDE":
                superseded_by = event["event_id"]
                state["supersedes"] = payload["supersedes"]
            elif event["event_type"] == "MISSION_COMPILED":
                state["mission_id"] = payload["mission_id"]
            last_event = event
        return {
            "entity_id": entity_id,
            "state": state,
            "last_event_id": last_event["event_id"] if last_event else None,
            "last_event_hash": last_event["event_hash"] if last_event else None,
            "event_count": len(events),
            "superseded_by_event": superseded_by,
        }

    def save_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        mission_id = mission["mission_id"]
        contract_sha = mission["contract_sha256"]
        payload = canonical_json(mission)
        inserted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT contract_sha256 FROM mission_contracts WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if existing:
                if existing["contract_sha256"] != contract_sha:
                    raise ValueError("mission_id conflict")
                return {"state": "IDEMPOTENT_REPLAY", "mission_id": mission_id}
            connection.execute(
                "INSERT INTO mission_contracts VALUES(?,?,?,?)",
                (mission_id, payload, contract_sha, inserted_at),
            )
        return {"state": "SAVED", "mission_id": mission_id}

    def get_mission(self, mission_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT contract_json FROM mission_contracts WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
        return json.loads(row["contract_json"]) if row else None
