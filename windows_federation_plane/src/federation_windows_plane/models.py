from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping


ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ALLOWED_TASKS = frozenset({"health", "inventory", "hash_workspace_file"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("TIMESTAMP_MUST_BE_UTC_Z")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None:
        raise ValueError("TIMESTAMP_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class TaskEnvelope:
    schema: str
    task_id: str
    correlation_id: str
    issued_by: str
    task_type: str
    issued_at: str
    expires_at: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    effect: str = "READ_ONLY"

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TaskEnvelope":
        expected = {
            "schema", "task_id", "correlation_id", "issued_by", "task_type",
            "issued_at", "expires_at", "parameters", "effect",
        }
        unknown = sorted(set(raw) - expected)
        if unknown:
            raise ValueError("UNKNOWN_ENVELOPE_FIELDS:" + ",".join(unknown))
        required = expected - {"parameters", "effect"}
        missing = sorted(key for key in required if raw.get(key) in (None, ""))
        if missing:
            raise ValueError("MISSING_ENVELOPE_FIELDS:" + ",".join(missing))
        return cls(
            schema=str(raw["schema"]),
            task_id=str(raw["task_id"]),
            correlation_id=str(raw["correlation_id"]),
            issued_by=str(raw["issued_by"]),
            task_type=str(raw["task_type"]),
            issued_at=str(raw["issued_at"]),
            expires_at=str(raw["expires_at"]),
            parameters=raw.get("parameters") or {},
            effect=str(raw.get("effect") or "READ_ONLY"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "TaskEnvelope":
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("ENVELOPE_OBJECT_REQUIRED")
        return cls.from_mapping(value)

    def validate(self, *, now: datetime | None = None) -> None:
        if self.schema != "FEDERATION-WINDOWS-TASK-V1":
            raise ValueError("UNSUPPORTED_TASK_SCHEMA")
        for label, value in (("TASK", self.task_id), ("CORRELATION", self.correlation_id)):
            if not ID_PATTERN.fullmatch(value):
                raise ValueError(f"{label}_ID_INVALID")
        if self.issued_by != "FUSE/FDOF":
            raise ValueError("UNTRUSTED_TASK_ISSUER")
        if self.task_type not in ALLOWED_TASKS:
            raise ValueError("TASK_TYPE_NOT_ALLOWLISTED")
        if self.effect != "READ_ONLY":
            raise ValueError("EFFECT_NOT_AUTHORIZED")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("PARAMETERS_OBJECT_REQUIRED")
        issued = parse_utc(self.issued_at)
        expires = parse_utc(self.expires_at)
        current = now or datetime.now(timezone.utc)
        if expires <= issued:
            raise ValueError("INVALID_TASK_TIME_WINDOW")
        if current > expires:
            raise ValueError("TASK_EXPIRED")
        if issued > current.replace(microsecond=current.microsecond):
            raise ValueError("TASK_NOT_YET_VALID")
        if (expires - issued).total_seconds() > 900:
            raise ValueError("TASK_TTL_EXCEEDS_900_SECONDS")


@dataclass(frozen=True)
class TaskReceipt:
    schema: str
    task_id: str
    correlation_id: str
    task_type: str
    state: str
    started_at: str
    completed_at: str
    runner: Mapping[str, Any]
    result: Mapping[str, Any]
    task_sha256: str
    result_sha256: str
    effect: str = "READ_ONLY"
    truth_boundary: str = (
        "This receipt proves only the exact allowlisted task on the identified Windows runner. "
        "It does not prove owner-workstation installation, broader provider authority, or production value."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def task_sha256(task: TaskEnvelope) -> str:
    encoded = json.dumps(
        asdict(task), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
