from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock
from time import time
from typing import Any


@dataclass(frozen=True)
class Event:
    sequence: int
    timestamp: float
    mission_id: str
    event_type: str
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str


class LedgerIntegrityError(RuntimeError):
    pass


class JsonlLedger:
    """Append-only hash-chained ledger with deterministic replay."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._lock = RLock()

    @staticmethod
    def _digest(sequence: int, timestamp: float, mission_id: str, event_type: str,
                payload: dict[str, Any], previous_hash: str) -> str:
        body = {"sequence": sequence, "timestamp": timestamp, "mission_id": mission_id,
                "event_type": event_type, "payload": payload, "previous_hash": previous_hash}
        return sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def events(self) -> list[Event]:
        with self._lock:
            result: list[Event] = []
            for line in self.path.read_text().splitlines():
                if line.strip():
                    result.append(Event(**json.loads(line)))
            return result

    def append(self, mission_id: str, event_type: str, payload: dict[str, Any]) -> Event:
        with self._lock:
            prior = self.events()
            sequence = len(prior) + 1
            previous_hash = prior[-1].event_hash if prior else "GENESIS"
            timestamp = time()
            event_hash = self._digest(sequence, timestamp, mission_id, event_type, payload, previous_hash)
            event = Event(sequence, timestamp, mission_id, event_type, payload, previous_hash, event_hash)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.__dict__, sort_keys=True) + "\n")
                handle.flush()
            return event

    def verify(self) -> bool:
        previous = "GENESIS"
        for expected, event in enumerate(self.events(), 1):
            if event.sequence != expected or event.previous_hash != previous:
                raise LedgerIntegrityError("sequence or chain mismatch")
            actual = self._digest(event.sequence, event.timestamp, event.mission_id,
                                  event.event_type, event.payload, event.previous_hash)
            if actual != event.event_hash:
                raise LedgerIntegrityError("event hash mismatch")
            previous = event.event_hash
        return True

    def mission_events(self, mission_id: str) -> list[Event]:
        return [event for event in self.events() if event.mission_id == mission_id]

