from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
import hashlib

from .models import utc_now_iso, canonical_json


ALLOWED_EVENT_TYPES = {
    "SUCCESS", "FAILURE", "CONSTRAINT", "CORRECTION", "RECOVERY",
    "INNOVATION_CANDIDATE", "EXPERIMENT_RESULT", "NEGATIVE_RESULT",
    "CAPABILITY_REDISCOVERY_TRIGGER",
}


@dataclass(frozen=True)
class LearningEvent:
    event_type: str
    category: str
    payload: Mapping[str, Any]
    previous_hash: str
    created_at: str = field(default_factory=utc_now_iso)
    event_hash: str = ""

    @staticmethod
    def calculate_hash(event_type: str, category: str, payload: Mapping[str, Any], previous_hash: str, created_at: str) -> str:
        body = {"event_type": event_type, "category": category, "payload": payload, "previous_hash": previous_hash, "created_at": created_at}
        return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


class LearningLedger:
    """Append-only hash-linked in-memory ledger; persistence belongs in the external evidence plane."""

    def __init__(self) -> None:
        self._events: list[LearningEvent] = []

    def append(self, event_type: str, category: str, payload: Mapping[str, Any]) -> LearningEvent:
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"unsupported learning event type: {event_type}")
        prev = self._events[-1].event_hash if self._events else "GENESIS"
        created = utc_now_iso()
        digest = LearningEvent.calculate_hash(event_type, category, payload, prev, created)
        event = LearningEvent(event_type, category, dict(payload), prev, created, digest)
        self._events.append(event)
        return event

    def events(self) -> tuple[LearningEvent, ...]:
        return tuple(self._events)

    def verify(self) -> bool:
        previous = "GENESIS"
        for event in self._events:
            if event.previous_hash != previous:
                return False
            expected = LearningEvent.calculate_hash(event.event_type, event.category, event.payload, event.previous_hash, event.created_at)
            if expected != event.event_hash:
                return False
            previous = event.event_hash
        return True
