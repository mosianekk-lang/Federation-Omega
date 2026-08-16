from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from .models import FederationEvent


EventHandler = Callable[[FederationEvent], object]


class EventBus:
    """In-memory deterministic event router with exactly-once idempotency keys.

    This is a source-level reference primitive. Durable provider-backed event
    delivery is a separate maturity gate.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._processed_keys: set[str] = set()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def emit(self, event: FederationEvent) -> list[object]:
        if event.idempotency_key in self._processed_keys:
            return []

        self._processed_keys.add(event.idempotency_key)
        results: list[object] = []
        for handler in self._subscribers.get(event.event_type, []):
            results.append(handler(event))
        for handler in self._subscribers.get("*", []):
            results.append(handler(event))
        return results

    def has_processed(self, idempotency_key: str) -> bool:
        return idempotency_key in self._processed_keys
