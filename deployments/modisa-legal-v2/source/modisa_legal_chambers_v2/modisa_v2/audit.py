from __future__ import annotations

from typing import Any

from .canonical import canonical_json, sha256_text
from .db import Repository
from .ids import new_id


AUDIT_GENESIS = "0" * 64


class AuditLog:
    def __init__(self, repo: Repository):
        self.repo = repo

    def append(
        self,
        *,
        actor_id: str,
        event_type: str,
        payload: dict[str, Any],
        matter_id: str | None = None,
        object_id: str | None = None,
    ) -> str:
        event_id = new_id("AUD")
        created_at = self.repo.now()
        with self.repo.connect(immediate=True) as conn:
            last = conn.execute(
                "SELECT event_hash FROM audit_events ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            previous_hash = str(last["event_hash"]) if last else AUDIT_GENESIS
            body = {
                "event_id": event_id,
                "matter_id": matter_id,
                "actor_id": actor_id,
                "event_type": event_type,
                "object_id": object_id,
                "payload": payload,
                "previous_hash": previous_hash,
                "created_at": created_at,
            }
            event_hash = sha256_text(canonical_json(body))
            conn.execute(
                """INSERT INTO audit_events(
                   event_id,matter_id,actor_id,event_type,object_id,payload_json,
                   previous_hash,event_hash,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    matter_id,
                    actor_id,
                    event_type,
                    object_id,
                    self.repo.dumps(payload),
                    previous_hash,
                    event_hash,
                    created_at,
                ),
            )
        return event_id

    def verify(self) -> tuple[bool, str | None]:
        rows = self.repo.fetch_all("SELECT * FROM audit_events ORDER BY created_at, rowid")
        previous = AUDIT_GENESIS
        for row in rows:
            if row["previous_hash"] != previous:
                return False, row["event_id"]
            body = {
                "event_id": row["event_id"],
                "matter_id": row["matter_id"],
                "actor_id": row["actor_id"],
                "event_type": row["event_type"],
                "object_id": row["object_id"],
                "payload": self.repo.loads(row["payload_json"], {}),
                "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            if sha256_text(canonical_json(body)) != row["event_hash"]:
                return False, row["event_id"]
            previous = row["event_hash"]
        return True, None
