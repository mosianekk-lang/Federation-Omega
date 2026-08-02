"""Pure append-only local event ledger with full semantic readback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .contracts import EventType, canonicalize, digest, enum_value, parse_utc
from .errors import ContractError
from .privacy import require_code, require_hash, strict_json_loads, validate_explicit_metadata

GENESIS_HASH = "sha256:" + "0" * 64
EVENT_METADATA_SCHEMAS = {
    EventType.NODE_REGISTERED: {"node_code": "code", "state_code": "code"},
    EventType.ENVELOPE_ACCEPTED: {"envelope_hash": "hash", "node_code": "code"},
    EventType.RECOMMENDATION_EMITTED: {"capability_hash": "hash", "state_code": "code"},
    EventType.RECEIPT_RECORDED: {"receipt_hash": "hash", "node_code": "code"},
    EventType.STOP_GENERATION_ADVANCED: {"control_generation": "integer", "state_code": "code"},
    EventType.RESPAWN_VERIFIED: {"manifest_hash": "hash", "state_code": "code"},
}


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    sequence: int
    event_type: EventType
    entity_code: str
    occurred_at: str
    control_generation: int
    payload_hash: str
    previous_hash: str
    event_hash: str

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise ContractError("INVALID_LEDGER_SEQUENCE")
        object.__setattr__(self, "event_type", enum_value(EventType, self.event_type, field="event_type"))
        require_code(self.entity_code, field="entity_code")
        parse_utc(self.occurred_at, field="occurred_at")
        if isinstance(self.control_generation, bool) or not isinstance(self.control_generation, int) or self.control_generation < 0:
            raise ContractError("INVALID_CONTROL_GENERATION")
        for name in ("payload_hash", "previous_hash", "event_hash"):
            require_hash(getattr(self, name), field=name)

    def hash_body(self) -> dict[str, Any]:
        value = canonicalize(self)
        value.pop("event_hash")
        return value


@dataclass(frozen=True, slots=True)
class LedgerReadback:
    valid: bool
    event_count: int
    tail_hash: str
    control_generation: int
    state_digest: str


@dataclass(frozen=True, slots=True)
class ImmutableEventLedger:
    events: tuple[LedgerEvent, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.events, (tuple, list)):
            raise ContractError("LEDGER_EVENTS_SEQUENCE_REQUIRED")
        snapshot = tuple(self.events)
        if any(not isinstance(item, LedgerEvent) for item in snapshot):
            raise ContractError("LEDGER_EVENT_ITEM_REQUIRED")
        object.__setattr__(self, "events", snapshot)

    @property
    def tail_hash(self) -> str:
        return self.events[-1].event_hash if self.events else GENESIS_HASH

    def append(
        self,
        *,
        event_type: EventType,
        entity_code: str,
        occurred_at: str,
        control_generation: int,
        payload: dict[str, Any],
    ) -> "ImmutableEventLedger":
        event_type = enum_value(EventType, event_type, field="event_type")
        if self.events and control_generation < self.events[-1].control_generation:
            raise ContractError("CONTROL_GENERATION_ROLLBACK")
        safe_payload = validate_explicit_metadata(
            payload,
            schema=EVENT_METADATA_SCHEMAS[event_type],
        )
        payload_hash = digest(safe_payload)
        placeholder = GENESIS_HASH
        event = LedgerEvent(
            sequence=len(self.events) + 1,
            event_type=event_type,
            entity_code=entity_code,
            occurred_at=occurred_at,
            control_generation=control_generation,
            payload_hash=payload_hash,
            previous_hash=self.tail_hash,
            event_hash=placeholder,
        )
        event = LedgerEvent(**{**canonicalize(event), "event_hash": digest(event.hash_body())})
        return ImmutableEventLedger(self.events + (event,))

    def verify(self) -> bool:
        previous = GENESIS_HASH
        previous_generation = 0
        for index, event in enumerate(self.events, start=1):
            if event.sequence != index or event.previous_hash != previous:
                return False
            if digest(event.hash_body()) != event.event_hash:
                return False
            if event.control_generation < previous_generation:
                return False
            previous = event.event_hash
            previous_generation = event.control_generation
        return True

    def semantic_readback(self, *, expected_count: int, expected_tail: str, expected_generation: int) -> LedgerReadback:
        require_hash(expected_tail, field="expected_tail")
        actual_generation = self.events[-1].control_generation if self.events else 0
        valid = (
            self.verify()
            and expected_count == len(self.events)
            and expected_tail == self.tail_hash
            and expected_generation == actual_generation
        )
        return LedgerReadback(
            valid=valid,
            event_count=len(self.events),
            tail_hash=self.tail_hash,
            control_generation=actual_generation,
            state_digest=digest([canonicalize(item) for item in self.events]),
        )

    def to_jsonl(self) -> str:
        return "".join(json.dumps(canonicalize(event), sort_keys=True, separators=(",", ":")) + "\n" for event in self.events)

    @classmethod
    def from_jsonl(cls, payload: str) -> "ImmutableEventLedger":
        if not isinstance(payload, str) or len(payload.encode("utf-8")) > 1_048_576:
            raise ContractError("LEDGER_PAYLOAD_INVALID_OR_OVERSIZED")
        events: list[LedgerEvent] = []
        for line_number, line in enumerate(payload.splitlines(), start=1):
            try:
                value = strict_json_loads(line, field=f"ledger_line_{line_number}")
                events.append(LedgerEvent(**value))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ContractError(f"INVALID_LEDGER_LINE:{line_number}") from exc
        ledger = cls(tuple(events))
        if not ledger.verify():
            raise ContractError("LEDGER_CHAIN_INVALID")
        return ledger
