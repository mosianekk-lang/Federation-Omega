from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .store import FabricStore
from .util import parse_utc


class EstateTwin:
    def __init__(self, store: FabricStore):
        self.store = store

    def ingest(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        counts = self.store.apply_snapshot(snapshot)
        readback = self.store.integrity_check()
        return {
            "state": "SNAPSHOT_INGESTED",
            "counts": counts,
            "integrity": readback,
            "provider_execution_inherited": False,
        }

    def freshness(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        rows = []
        for heartbeat in self.store.list_documents("heartbeats"):
            age = max(0.0, (now - parse_utc(heartbeat["observed_at"])).total_seconds())
            rows.append({**heartbeat, "age_seconds": age})
        return sorted(rows, key=lambda row: row["node_id"])

    def public_readback(self) -> dict[str, Any]:
        snapshot = self.store.snapshot()
        snapshot["truth_boundary"] = (
            "Estate records and connector observations do not inherit provider authority "
            "or operational proof."
        )
        return snapshot

