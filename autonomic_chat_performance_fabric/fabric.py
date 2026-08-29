from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class Event:
    namespace: str
    conversation: str
    sequence: int
    event_class: str
    payload: str
    previous_hash: str = ""
    source_version: str = ""
    privacy_class: str = "GOVERNED_PRIVATE"

    @property
    def content_hash(self) -> str:
        return sha256(self.payload.encode()).hexdigest()

    @property
    def event_hash(self) -> str:
        return sha256(_canonical(asdict(self) | {"content_hash": self.content_hash})).hexdigest()


class ContentAddressedEventLog:
    """Append-only, deduplicated event log with per-conversation hash chains."""

    def __init__(self) -> None:
        self._events: dict[str, Event] = {}
        self._heads: dict[tuple[str, str], str] = {}
        self._content: dict[str, str] = {}

    def append(self, event: Event) -> dict[str, object]:
        key = (event.namespace, event.conversation)
        if event.event_hash in self._events:
            return {"state": "IDEMPOTENT", "event_hash": event.event_hash}
        expected = self._heads.get(key, "")
        if event.previous_hash != expected:
            raise ValueError("STALE_OR_CONFLICTED_HEAD")
        self._events[event.event_hash] = event
        self._content.setdefault(event.content_hash, event.payload)
        self._heads[key] = event.event_hash
        return {"state": "APPENDED", "event_hash": event.event_hash}

    def head(self, namespace: str, conversation: str) -> str:
        return self._heads.get((namespace, conversation), "")

    def events(self, namespace: str, conversation: str) -> list[Event]:
        items = [
            event for event in self._events.values()
            if event.namespace == namespace and event.conversation == conversation
        ]
        return sorted(items, key=lambda item: item.sequence)

    def verify(self, namespace: str, conversation: str) -> bool:
        previous = ""
        for event in self.events(namespace, conversation):
            if event.previous_hash != previous:
                return False
            previous = event.event_hash
        return previous == self.head(namespace, conversation)


@dataclass(frozen=True)
class Health:
    available: bool
    latency_ms: float
    failure_rate: float
    capacity: float


@dataclass(frozen=True)
class Route:
    name: str
    work_classes: frozenset[str]
    authority: bool
    privacy_classes: frozenset[str]
    incremental_cost: float = 0


class AdaptiveRouter:
    """Fail-closed route selection with health, authority and privacy gates."""

    def select(
        self,
        work_class: str,
        privacy_class: str,
        routes: Iterable[Route],
        health: dict[str, Health],
    ) -> Route:
        ranked: list[tuple[float, Route]] = []
        for route in routes:
            state = health.get(route.name)
            if (
                not route.authority
                or route.incremental_cost > 0
                or work_class not in route.work_classes
                or privacy_class not in route.privacy_classes
                or not state
                or not state.available
                or state.capacity <= 0
            ):
                continue
            score = (
                4 * state.capacity
                - min(state.latency_ms / 1000, 5)
                - 5 * state.failure_rate
            )
            ranked.append((score, route))
        if not ranked:
            raise RuntimeError("NO_AUTHORIZED_HEALTHY_ROUTE")
        ranked.sort(key=lambda pair: (-pair[0], pair[1].name))
        return ranked[0][1]


class ContextCompiler:
    """Build bounded current context without replaying full history."""

    def __init__(self, maximum_chars: int = 28_000) -> None:
        if maximum_chars < 1_000:
            raise ValueError("maximum_chars too small")
        self.maximum_chars = maximum_chars

    def compile(
        self,
        instruction: str,
        controlling_rules: list[str],
        verified_facts: list[str],
        unresolved: list[str],
        recent_events: list[Event],
    ) -> str:
        sections = [
            ("CURRENT INSTRUCTION", [instruction]),
            ("CONTROLLING RULES", controlling_rules),
            ("VERIFIED FACTS", verified_facts),
            ("UNRESOLVED", unresolved),
            ("RECENT DELTAS", [event.payload for event in recent_events[-8:]]),
        ]
        rendered = "\n".join(
            f"{title}\n" + "\n".join(f"- {item}" for item in items if item)
            for title, items in sections
        )
        if len(rendered) <= self.maximum_chars:
            return rendered
        fixed = "\n".join(
            f"{title}\n" + "\n".join(f"- {item}" for item in items if item)
            for title, items in sections[:-1]
        )
        budget = max(0, self.maximum_chars - len(fixed) - 20)
        return fixed + "\nRECENT DELTAS\n" + rendered[-budget:]
