from __future__ import annotations

"""Durable SQLite journal for Federation Living State.

Tables are prefixed ``living_state_`` so the store can share the same SQLite
file as the existing Bubbles Federation Governor Ω4 registry without competing
for its canonical tables. The store persists only caller-supplied world-model
projections; it does not discover private provider data itself.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from .world_model import FabricError, LivingWorldModel, digest


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class StoreReceipt:
    fabric_id: str
    event_count: int
    event_head_digest: str
    snapshot_sha256: str
    store_readback_verified: bool
    external_effects: int = 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


class LivingStateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS living_state_events (
                fabric_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_digest TEXT NOT NULL,
                prior_digest TEXT NOT NULL,
                event_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (fabric_id, sequence),
                UNIQUE (fabric_id, event_digest)
            );
            CREATE TABLE IF NOT EXISTS living_state_snapshots (
                fabric_id TEXT NOT NULL,
                snapshot_sha256 TEXT NOT NULL,
                event_head_digest TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (fabric_id, snapshot_sha256)
            );
            CREATE INDEX IF NOT EXISTS living_state_events_head_idx
              ON living_state_events(fabric_id, sequence DESC);
            CREATE INDEX IF NOT EXISTS living_state_snapshots_head_idx
              ON living_state_snapshots(fabric_id, event_count DESC);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "LivingStateStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def seal(self, model: LivingWorldModel, *, now: str, fabric_id: str = "FEDERATION") -> StoreReceipt:
        if not model.verify_event_chain():
            raise FabricError("cannot seal invalid event chain")
        events = model.export_event_log()
        snapshot = model.snapshot(now=now)
        created_at = _utc_now()
        cursor = self.connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            existing = cursor.execute(
                "SELECT sequence,event_digest FROM living_state_events WHERE fabric_id=? ORDER BY sequence",
                (fabric_id,),
            ).fetchall()
            existing_map = {int(row["sequence"]): str(row["event_digest"]) for row in existing}
            for event in events:
                sequence = int(event["sequence"])
                event_digest = str(event["event_digest"])
                if sequence in existing_map:
                    if existing_map[sequence] != event_digest:
                        raise FabricError("durable journal sequence collision")
                    continue
                cursor.execute(
                    """INSERT INTO living_state_events
                       (fabric_id,sequence,event_digest,prior_digest,event_type,object_id,payload_json,created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        fabric_id,
                        sequence,
                        event_digest,
                        str(event["prior_digest"]),
                        str(event["event_type"]),
                        str(event["object_id"]),
                        json.dumps(event["payload"], sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str),
                        created_at,
                    ),
                )
            cursor.execute(
                """INSERT OR IGNORE INTO living_state_snapshots
                   (fabric_id,snapshot_sha256,event_head_digest,event_count,observed_at,payload_json,created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    fabric_id,
                    snapshot["snapshot_sha256"],
                    snapshot["event_head_digest"],
                    snapshot["event_count"],
                    now,
                    json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str),
                    created_at,
                ),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

        restored = self.restore(fabric_id=fabric_id)
        restored_snapshot = restored.snapshot(now=now)
        if restored_snapshot["snapshot_sha256"] != snapshot["snapshot_sha256"]:
            raise FabricError("durable store semantic readback mismatch")
        rows = self.connection.execute(
            "SELECT COUNT(*) AS n, MAX(sequence) AS seq FROM living_state_events WHERE fabric_id=?",
            (fabric_id,),
        ).fetchone()
        verified = int(rows["n"]) == len(events) and int(rows["seq"] or 0) == len(events)
        if not verified:
            raise FabricError("durable event count readback mismatch")
        return StoreReceipt(
            fabric_id=fabric_id,
            event_count=len(events),
            event_head_digest=model.event_head_digest,
            snapshot_sha256=snapshot["snapshot_sha256"],
            store_readback_verified=True,
            external_effects=model.external_effects,
        )

    def event_log(self, *, fabric_id: str = "FEDERATION") -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            """SELECT sequence,event_digest,prior_digest,event_type,object_id,payload_json
               FROM living_state_events WHERE fabric_id=? ORDER BY sequence""",
            (fabric_id,),
        ).fetchall()
        return tuple(
            {
                "sequence": int(row["sequence"]),
                "event_digest": str(row["event_digest"]),
                "prior_digest": str(row["prior_digest"]),
                "event_type": str(row["event_type"]),
                "object_id": str(row["object_id"]),
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        )

    def restore(self, *, fabric_id: str = "FEDERATION") -> LivingWorldModel:
        return LivingWorldModel.replay(self.event_log(fabric_id=fabric_id))

    def latest_snapshot(self, *, fabric_id: str = "FEDERATION") -> dict[str, Any] | None:
        row = self.connection.execute(
            """SELECT payload_json FROM living_state_snapshots
               WHERE fabric_id=? ORDER BY event_count DESC, created_at DESC LIMIT 1""",
            (fabric_id,),
        ).fetchone()
        return None if row is None else json.loads(row["payload_json"])


__all__ = ["LivingStateStore", "StoreReceipt"]
