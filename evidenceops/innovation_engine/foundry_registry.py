from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

from .registry import InnovationRegistry, STATES


class FoundryInnovationRegistry(InnovationRegistry):
    """Extends the existing registry without rewriting historical lane logic."""

    def get_lane(self, lane_id: str):
        with self._connect() as connection:
            lane = connection.execute(
                "SELECT * FROM lanes WHERE lane_id=?", (lane_id,)
            ).fetchone()
        if lane is None:
            raise KeyError(f"Unknown lane: {lane_id}")
        return lane

    def ensure_lane(
        self,
        *,
        lane_id: str,
        title: str,
        objective: str,
        state: str,
        priority: float,
        next_action: str,
        proof_state: str,
    ) -> bool:
        if state not in STATES:
            raise ValueError(f"Unsupported state: {state}")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT lane_id FROM lanes WHERE lane_id=?", (lane_id,)
            ).fetchone()
            if existing is not None:
                return False
            connection.execute(
                "INSERT INTO lanes VALUES(?,?,?,?,?,?,?,?)",
                (
                    lane_id,
                    title,
                    objective,
                    state,
                    priority,
                    next_action,
                    proof_state,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return True

    def synchronise_catalog(
        self,
        catalog: Mapping[str, object],
        *,
        default_state: str = "READY",
        starting_priority: float = 100.0,
    ) -> dict[str, object]:
        rows = catalog.get("algorithms")
        if not isinstance(rows, list):
            raise ValueError("catalog.algorithms must be a list")
        created: list[str] = []
        preserved: list[str] = []
        seen: set[str] = set()
        for index, raw in enumerate(rows):
            if not isinstance(raw, Mapping):
                raise ValueError(f"catalog algorithm {index} must be an object")
            algorithm_id = str(raw.get("algorithm_id") or "").strip()
            name = str(raw.get("name") or "").strip()
            purpose = str(raw.get("purpose") or "").strip()
            if not algorithm_id or not name or not purpose:
                raise ValueError(
                    f"catalog algorithm {index} requires algorithm_id, name and purpose"
                )
            if algorithm_id in seen:
                raise ValueError(f"duplicate catalog algorithm_id: {algorithm_id}")
            seen.add(algorithm_id)
            created_now = self.ensure_lane(
                lane_id=algorithm_id,
                title=name,
                objective=purpose,
                state=default_state,
                priority=max(1.0, starting_priority - float(index)),
                next_action="execute deterministic bounded test and evaluate",
                proof_state=str(raw.get("maturity") or "SOURCE_IMPLEMENTED_PENDING_TEST"),
            )
            (created if created_now else preserved).append(algorithm_id)
        with self._connect() as connection:
            registered = {
                row[0] for row in connection.execute("SELECT lane_id FROM lanes")
            }
        missing = sorted(seen - registered)
        return {
            "schema": "EVIDENCEOPS_CATALOG_REGISTRY_SYNC_V1",
            "catalog_algorithm_count": len(seen),
            "created_lane_ids": created,
            "preserved_lane_ids": preserved,
            "missing_lane_ids": missing,
            "complete": not missing,
        }
