from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import re
from typing import Any

from .hashing import sha256_value

SAFE_ID = re.compile(r"^[A-Z0-9][A-Z0-9._:/-]{2,127}$")
AUTHORITY_ORDER = {"A0": 0, "A1": 1, "A2": 2, "A3": 3}
EVENT_TYPES = {"STATE_SET", "STATE_PATCH", "STATUS_SET", "SUPERSEDE", "MISSION_COMPILED"}


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


@dataclass(frozen=True)
class Event:
    event_id: str
    entity_id: str
    event_type: str
    occurred_at: str
    observed_at: str
    source: str
    authority: str
    payload: dict[str, Any]

    def validate(self) -> None:
        for field in ("event_id", "entity_id", "source"):
            if not SAFE_ID.fullmatch(str(getattr(self, field))):
                raise ValueError(f"invalid {field}")
        if self.event_type not in EVENT_TYPES:
            raise ValueError("unsupported event_type")
        if self.authority not in AUTHORITY_ORDER:
            raise ValueError("unsupported authority")
        parse_timestamp(self.occurred_at)
        parse_timestamp(self.observed_at)
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be an object")
        if self.event_type == "STATE_PATCH" and not isinstance(self.payload.get("patch"), dict):
            raise ValueError("STATE_PATCH requires payload.patch")
        if self.event_type == "STATE_SET" and not isinstance(self.payload.get("state"), dict):
            raise ValueError("STATE_SET requires payload.state")
        if self.event_type == "STATUS_SET" and not isinstance(self.payload.get("status"), str):
            raise ValueError("STATUS_SET requires payload.status")
        if self.event_type == "SUPERSEDE" and not SAFE_ID.fullmatch(str(self.payload.get("supersedes", ""))):
            raise ValueError("SUPERSEDE requires a valid supersedes ID")

    def body(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def body_hash(self) -> str:
        return sha256_value(self.body())


@dataclass(frozen=True)
class MissionContract:
    mission_id: str
    objective: str
    success_criteria: tuple[str, ...]
    authority_ceiling: str
    deadline: str | None
    budget: dict[str, Any]
    source_requirements: tuple[str, ...]
    constraints: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    rollback_required: bool
    external_effects_allowed: bool
    contract_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
