from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Iterable


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    event_id: str
    stream_id: str
    stream_version: int
    event_type: str
    recorded_at: str
    valid_at: str
    idempotency_key: str
    truth_class: str
    privacy_class: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_refs: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    causal_parent_ids: tuple[str, ...] = ()
    directive_id: str | None = None
    mission_id: str | None = None
    workstream_id: str | None = None
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    schema_version: int = 1

    def validate(self) -> "MemoryEvent":
        required = (self.event_id, self.stream_id, self.event_type, self.recorded_at, self.valid_at, self.idempotency_key)
        if not all(str(item).strip() for item in required):
            raise ValueError("MEMORY_EVENT_REQUIRED_FIELD_MISSING")
        if self.stream_version < 1 or self.schema_version < 1:
            raise ValueError("MEMORY_EVENT_VERSION_INVALID")
        if self.privacy_class == "GLOBAL" and any(key.lower() in {"secret", "password", "credential", "medical_raw", "private_raw"} for key in self.payload):
            raise ValueError("GLOBAL_MEMORY_SENSITIVE_PAYLOAD_REJECTED")
        return self

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class AppendReceipt:
    event_id: str
    stream_id: str
    stream_version: int
    event_digest: str
    state: str


class InMemoryEventStore:
    """Deterministic shadow event store; no provider durability is claimed."""

    def __init__(self) -> None:
        self._streams: dict[str, list[MemoryEvent]] = {}
        self._idempotency: dict[str, tuple[str, str]] = {}

    def version(self, stream_id: str) -> int:
        return len(self._streams.get(stream_id, ()))

    def append(self, event: MemoryEvent, *, expected_version: int) -> AppendReceipt:
        event.validate()
        current = self.version(event.stream_id)
        if current != expected_version:
            raise ValueError("MEMORY_STREAM_VERSION_CONFLICT")
        if event.stream_version != current + 1:
            raise ValueError("MEMORY_STREAM_EVENT_VERSION_MISMATCH")
        fingerprint = event.digest()
        prior = self._idempotency.get(event.idempotency_key)
        if prior:
            prior_event_id, prior_digest = prior
            if prior_digest != fingerprint:
                raise ValueError("MEMORY_IDEMPOTENCY_PARAMETER_MISMATCH")
            return AppendReceipt(prior_event_id, event.stream_id, event.stream_version, prior_digest, "IDEMPOTENT_REPLAY")
        self._streams.setdefault(event.stream_id, []).append(event)
        self._idempotency[event.idempotency_key] = (event.event_id, fingerprint)
        return AppendReceipt(event.event_id, event.stream_id, event.stream_version, fingerprint, "APPENDED")

    def stream(self, stream_id: str) -> tuple[MemoryEvent, ...]:
        return tuple(self._streams.get(stream_id, ()))

    def all_events(self) -> tuple[MemoryEvent, ...]:
        return tuple(event for stream in sorted(self._streams) for event in self._streams[stream])


@dataclass(frozen=True, slots=True)
class ProjectionState:
    stream_id: str
    as_of_recorded_at: str | None
    event_count: int
    current: dict[str, Any]
    directive_ids: tuple[str, ...]
    mission_ids: tuple[str, ...]
    contradictions: tuple[tuple[str, str], ...]
    superseded_event_ids: tuple[str, ...]
    projection_hash: str


class ProjectionCompiler:
    def project(self, events: Iterable[MemoryEvent], *, as_of_recorded_at: str | None = None) -> ProjectionState:
        ordered = sorted(events, key=lambda event: (event.recorded_at, event.stream_version, event.event_id))
        if as_of_recorded_at is not None:
            ordered = [event for event in ordered if event.recorded_at <= as_of_recorded_at]
        current: dict[str, Any] = {}
        superseded: set[str] = set()
        contradictions: set[tuple[str, str]] = set()
        directives: set[str] = set()
        missions: set[str] = set()
        stream_id = ordered[0].stream_id if ordered else "EMPTY"
        for event in ordered:
            superseded.update(event.supersedes)
            for other in event.contradicts:
                contradictions.add(tuple(sorted((event.event_id, other))))
            if event.directive_id:
                directives.add(event.directive_id)
            if event.mission_id:
                missions.add(event.mission_id)
            if event.event_type in {"STATE_SET", "DECISION_ACCEPTED", "RESULT_VERIFIED", "BLOCKER_SET", "NEXT_ACTION_SET"}:
                for key, value in event.payload.items():
                    current[key] = value
            elif event.event_type == "STATE_UNSET":
                for key in event.payload.get("keys", ()):
                    current.pop(str(key), None)
        payload = {
            "stream_id": stream_id,
            "as_of_recorded_at": as_of_recorded_at,
            "event_count": len(ordered),
            "current": current,
            "directive_ids": sorted(directives),
            "mission_ids": sorted(missions),
            "contradictions": sorted(contradictions),
            "superseded_event_ids": sorted(superseded),
        }
        return ProjectionState(**payload, projection_hash=_digest(payload))


@dataclass(frozen=True, slots=True)
class MemoryDocument:
    memory_id: str
    text: str
    truth_class: str
    privacy_class: str
    source_refs: tuple[str, ...]
    workstream_id: str | None = None
    mission_id: str | None = None
    graph_keys: tuple[str, ...] = ()
    lexical_terms: tuple[str, ...] = ()
    embedding_ref: str | None = None
    token_cost: int = 1


class HybridRetrievalPlanner:
    """Provider-neutral retrieval planner; embeddings/graph engines remain adapters."""

    def select(self, documents: Iterable[MemoryDocument], *, query: str, token_budget: int, workstream_id: str | None = None) -> tuple[MemoryDocument, ...]:
        terms = {term.casefold() for term in query.split() if term.strip()}
        candidates: list[tuple[float, MemoryDocument]] = []
        for doc in documents:
            if workstream_id and doc.workstream_id not in {None, workstream_id}:
                continue
            lexical = {term.casefold() for term in doc.lexical_terms} | {term.casefold() for term in doc.text.split()}
            exact = len(terms & lexical) / max(1, len(terms))
            graph_bonus = 0.15 if terms & {item.casefold() for item in doc.graph_keys} else 0.0
            semantic_ready = 0.10 if doc.embedding_ref else 0.0
            truth_bonus = 0.15 if doc.truth_class in {"VERIFIED", "EVENT_TRUTH"} else 0.0
            candidates.append((exact + graph_bonus + semantic_ready + truth_bonus, doc))
        candidates.sort(key=lambda row: (-row[0], row[1].token_cost, row[1].memory_id))
        selected: list[MemoryDocument] = []
        used = 0
        for _, doc in candidates:
            if used + doc.token_cost > token_budget:
                continue
            selected.append(doc)
            used += doc.token_cost
        return tuple(selected)


class BibleRenderer:
    """Renders operational Bible sections from machine state; doctrine remains human-governed."""

    def render(self, projection: ProjectionState, *, doctrine_ref: str, memory_refs: Iterable[str]) -> dict[str, Any]:
        return {
            "schema": "CFBE-BIBLE-MEMORY-RENDER-V1",
            "doctrine_ref": doctrine_ref,
            "stream_id": projection.stream_id,
            "current_state": projection.current,
            "directives": list(projection.directive_ids),
            "missions": list(projection.mission_ids),
            "open_contradictions": [list(item) for item in projection.contradictions],
            "superseded_event_ids": list(projection.superseded_event_ids),
            "memory_refs": sorted(set(memory_refs)),
            "projection_hash": projection.projection_hash,
            "truth_boundary": [
                "rendered_bible_is_a_projection_not_primary_event_truth",
                "doctrine_prose_is_not_overwritten_by_runtime_projection",
                "provider_currentness_requires_fresh_readback_when_material",
            ],
        }
