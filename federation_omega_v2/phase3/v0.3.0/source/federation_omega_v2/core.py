from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

SAFE_ID = re.compile(r"^[A-Z0-9][A-Z0-9._:/-]{2,127}$")
STAGES = (
    "SOURCE_LOCK", "PROVENANCE", "CHRONOLOGY", "ELEMENT_MAP",
    "CONTRADICTION_SCAN", "GAP_SCHEDULE", "INTERNAL_BUNDLE",
    "BENCHMIND", "REVIEWGUARD", "OWNER_BRIEF",
)


def cjson(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value):
    return hashlib.sha256(cjson(value).encode()).hexdigest()


@dataclass(frozen=True)
class Event:
    event_id: str
    entity_id: str
    event_type: str
    observed_at: str
    source: str
    payload: dict[str, Any]
    authority: str = "A1"

    def body(self):
        if not SAFE_ID.fullmatch(self.event_id) or not SAFE_ID.fullmatch(self.entity_id) or not SAFE_ID.fullmatch(self.source):
            raise ValueError("invalid event identity")
        if self.authority != "A1":
            raise ValueError("authority must remain A1")
        if self.event_type not in {"STATE_SET", "STATE_PATCH", "MISSION_STAGE"}:
            raise ValueError("unsupported event")
        parsed = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be object")
        return asdict(self)


@dataclass(frozen=True)
class Relationship:
    source_id: str
    target_id: str
    relation_type: str

    def body(self):
        if not SAFE_ID.fullmatch(self.source_id) or not SAFE_ID.fullmatch(self.target_id):
            raise ValueError("invalid endpoint")
        if self.source_id == self.target_id:
            raise ValueError("self relationship prohibited")
        if not SAFE_ID.fullmatch(self.relation_type):
            raise ValueError("invalid relation")
        return asdict(self)

    @property
    def relation_id(self):
        return "REL-" + sha(self.body())[:24].upper()


class EventStore:
    def __init__(self, path):
        self.path = str(path)
        self._init()

    def connect(self):
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

    def _init(self):
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events(
                  seq INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT UNIQUE NOT NULL,
                  entity_id TEXT NOT NULL,
                  event_type TEXT NOT NULL,
                  observed_at TEXT NOT NULL,
                  source TEXT NOT NULL,
                  authority TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  previous_hash TEXT,
                  event_hash TEXT UNIQUE NOT NULL,
                  body_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_id,seq);
                CREATE TABLE IF NOT EXISTS relationships(
                  relation_id TEXT PRIMARY KEY,
                  source_id TEXT,
                  target_id TEXT,
                  relation_type TEXT,
                  body_hash TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS missions(
                  mission_id TEXT PRIMARY KEY,
                  mission_json TEXT NOT NULL,
                  mission_hash TEXT UNIQUE NOT NULL
                );
                """
            )

    def append(self, event: Event):
        body = event.body()
        body_hash = sha(body)
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT body_hash,event_hash,seq FROM events WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
            if existing:
                if existing["body_hash"] != body_hash:
                    raise ValueError("event_id conflict")
                return {
                    "state": "IDEMPOTENT_REPLAY",
                    "sequence": existing["seq"],
                    "event_hash": existing["event_hash"],
                }
            previous = connection.execute(
                "SELECT event_hash FROM events WHERE entity_id=? ORDER BY seq DESC LIMIT 1",
                (event.entity_id,),
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else None
            event_hash = sha({
                "body": body,
                "body_hash": body_hash,
                "previous_hash": previous_hash,
            })
            cursor = connection.execute(
                "INSERT INTO events(event_id,entity_id,event_type,observed_at,source,authority,payload,previous_hash,event_hash,body_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    event.event_id,
                    event.entity_id,
                    event.event_type,
                    event.observed_at,
                    event.source,
                    event.authority,
                    cjson(event.payload),
                    previous_hash,
                    event_hash,
                    body_hash,
                ),
            )
            return {
                "state": "APPENDED",
                "sequence": cursor.lastrowid,
                "event_hash": event_hash,
            }

    def add_relationship(self, relationship: Relationship):
        body = relationship.body()
        body_hash = sha(body)
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT body_hash FROM relationships WHERE relation_id=?",
                (relationship.relation_id,),
            ).fetchone()
            if existing:
                if existing["body_hash"] != body_hash:
                    raise ValueError("relationship conflict")
                return {"state": "IDEMPOTENT_REPLAY", "relation_id": relationship.relation_id}
            connection.execute(
                "INSERT INTO relationships VALUES(?,?,?,?,?)",
                (
                    relationship.relation_id,
                    relationship.source_id,
                    relationship.target_id,
                    relationship.relation_type,
                    body_hash,
                ),
            )
        return {"state": "ADDED", "relation_id": relationship.relation_id}

    def events(self, entity=None):
        query = "SELECT * FROM events"
        parameters = ()
        if entity:
            query += " WHERE entity_id=?"
            parameters = (entity,)
        query += " ORDER BY seq"
        with self.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [{**dict(row), "payload_obj": json.loads(row["payload"])} for row in rows]

    def relationships(self, system=None, direction="both"):
        query = "SELECT * FROM relationships"
        parameters = ()
        if system and direction == "out":
            query += " WHERE source_id=?"
            parameters = (system,)
        elif system and direction == "in":
            query += " WHERE target_id=?"
            parameters = (system,)
        elif system:
            query += " WHERE source_id=? OR target_id=?"
            parameters = (system, system)
        query += " ORDER BY relation_type,source_id,target_id"
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    def project(self, entity):
        state = {}
        last = None
        events = self.events(entity)
        for event in events:
            payload = event["payload_obj"]
            if event["event_type"] == "STATE_SET":
                state = dict(payload["state"])
            elif event["event_type"] == "STATE_PATCH":
                state.update(payload["patch"])
            elif event["event_type"] == "MISSION_STAGE":
                state.setdefault("stages", {})[payload["stage"]] = payload["status"]
            last = event
        return {
            "entity_id": entity,
            "state": state,
            "event_count": len(events),
            "last_event_id": last["event_id"] if last else None,
            "last_event_hash": last["event_hash"] if last else None,
        }

    def save_mission(self, mission):
        mission_hash = sha(mission)
        mission_id = mission["mission_id"]
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT mission_hash FROM missions WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
            if existing:
                if existing["mission_hash"] != mission_hash:
                    raise ValueError("mission conflict")
                return {"state": "IDEMPOTENT_REPLAY"}
            connection.execute(
                "INSERT INTO missions VALUES(?,?,?)",
                (mission_id, cjson(mission), mission_hash),
            )
        return {"state": "SAVED"}

    def mission(self, mission_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT mission_json FROM missions WHERE mission_id=?",
                (mission_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def verify(self):
        with self.connection() as connection:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
            entities = [row[0] for row in connection.execute("SELECT DISTINCT entity_id FROM events")]
            relationship_count = connection.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        event_count = 0
        for entity in entities:
            previous_hash = None
            for event in self.events(entity):
                body = {
                    "event_id": event["event_id"],
                    "entity_id": event["entity_id"],
                    "event_type": event["event_type"],
                    "observed_at": event["observed_at"],
                    "source": event["source"],
                    "payload": event["payload_obj"],
                    "authority": event["authority"],
                }
                body_hash = sha(body)
                event_hash = sha({
                    "body": body,
                    "body_hash": body_hash,
                    "previous_hash": previous_hash,
                })
                if body_hash != event["body_hash"] or event_hash != event["event_hash"] or event["previous_hash"] != previous_hash:
                    raise ValueError("hash mismatch")
                previous_hash = event["event_hash"]
                event_count += 1
        return {
            "quick_check": quick_check,
            "entity_count": len(entities),
            "event_count": event_count,
            "relationship_count": relationship_count,
        }


class CanonicalQueryService:
    def __init__(self, store):
        self.store = store

    def system(self, system_id):
        projection = self.store.project(system_id)
        return {
            **projection,
            "proof_state": "READBACK_VERIFIED" if projection["event_count"] else "UNKNOWN",
            "outgoing": self.store.relationships(system_id, "out"),
            "incoming": self.store.relationships(system_id, "in"),
        }
