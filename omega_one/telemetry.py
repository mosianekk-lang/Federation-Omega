"""Provider-neutral, secret-safe telemetry for the Omega-One work engine.

The journal is local and append-only.  It records hashes and redacted metadata,
never credentials or unbounded task payloads.  OpenTelemetry exporters may be
added by an adapter, but this module deliberately performs no network I/O.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading
from typing import Any, Mapping
from uuid import uuid4


_SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:api_?key|authorization|credential|password|secret|token)(?:$|_)",
    re.IGNORECASE,
)
_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def redact(value: Any, *, max_string: int = 512, max_items: int = 100) -> Any:
    """Return a bounded, recursively redacted telemetry-safe value."""
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                output["_truncated_items"] = len(value) - max_items
                break
            name = str(key)
            output[name] = "[REDACTED]" if _SENSITIVE_KEY.search(name) else redact(
                item, max_string=max_string, max_items=max_items
            )
        return output
    if isinstance(value, (list, tuple, set)):
        sequence = list(value)
        redacted = [redact(item, max_string=max_string, max_items=max_items) for item in sequence[:max_items]]
        if len(sequence) > max_items:
            redacted.append({"_truncated_items": len(sequence) - max_items})
        return redacted
    if isinstance(value, bytes):
        return {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, str) and len(value) > max_string:
        return value[:max_string] + f"…[truncated:{len(value) - max_string}]"
    return value


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    trace_flags: str = "01"

    @classmethod
    def new(cls) -> "TraceContext":
        return cls(secrets.token_hex(16), secrets.token_hex(8))

    @classmethod
    def parse(cls, value: str) -> "TraceContext":
        match = _TRACEPARENT.fullmatch(value.strip().lower())
        if not match or match.group(1) == "0" * 32 or match.group(2) == "0" * 16:
            raise ValueError("INVALID_TRACEPARENT")
        return cls(match.group(1), match.group(2), match.group(3))

    def child(self) -> "TraceContext":
        return TraceContext(self.trace_id, secrets.token_hex(8), self.trace_flags)

    @property
    def traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags}"


@dataclass(frozen=True)
class CloudEvent:
    id: str
    source: str
    type: str
    subject: str
    time: str
    data: Mapping[str, Any]
    datacontenttype: str = "application/json"
    specversion: str = "1.0"
    dataschema: str = "urn:omega-one:audit-event:v1"
    extensions: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        subject: str,
        data: Mapping[str, Any],
        source: str = "urn:omega-one:completion-engine",
        extensions: Mapping[str, Any] | None = None,
    ) -> "CloudEvent":
        if not event_type.strip() or not subject.strip():
            raise ValueError("EVENT_TYPE_AND_SUBJECT_REQUIRED")
        return cls(
            id=str(uuid4()),
            source=source,
            type=event_type,
            subject=subject,
            time=utc_now(),
            data=redact(data),
            extensions=redact(extensions or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        extensions = body.pop("extensions")
        body.update(extensions)
        return body


class HashChainedAuditJournal:
    """Durable JSONL audit journal with a deterministic hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def append(self, event: CloudEvent) -> dict[str, Any]:
        with self._lock:
            rows = self._rows()
            previous = rows[-1]["event_hash"] if rows else "GENESIS"
            envelope = {"previous_hash": previous, "event": event.to_dict()}
            record = {**envelope, "event_hash": digest(envelope)}
            encoded = canonical_json(record) + "\n"
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            return record

    def verify(self) -> bool:
        previous = "GENESIS"
        try:
            for row in self._rows():
                envelope = {"previous_hash": row["previous_hash"], "event": row["event"]}
                if row["previous_hash"] != previous or row["event_hash"] != digest(envelope):
                    return False
                previous = row["event_hash"]
            return True
        except (KeyError, json.JSONDecodeError, OSError, TypeError):
            return False

    def tail(self, count: int = 20) -> list[dict[str, Any]]:
        if count < 0:
            raise ValueError("COUNT_MUST_BE_NONNEGATIVE")
        return self._rows()[-count:] if count else []


class MetricsRegistry:
    """Small thread-safe metric store for deterministic tests and local operation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._samples: dict[str, list[float]] = {}

    def increment(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + float(amount)

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = float(value)

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._samples.setdefault(name, []).append(float(value))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            distributions = {}
            for name, samples in self._samples.items():
                ordered = sorted(samples)
                p95_index = max(0, min(len(ordered) - 1, int(0.95 * len(ordered)) - 1))
                distributions[name] = {
                    "count": len(samples),
                    "min": min(samples),
                    "max": max(samples),
                    "mean": sum(samples) / len(samples),
                    "p95": ordered[p95_index],
                }
            return {
                "counters": dict(sorted(self._counters.items())),
                "gauges": dict(sorted(self._gauges.items())),
                "distributions": dict(sorted(distributions.items())),
            }
