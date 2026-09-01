from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SpanKind(str, Enum):
    MISSION = "MISSION"
    WORKSTREAM = "WORKSTREAM"
    TASK = "TASK"
    AGENT = "AGENT"
    MODEL = "MODEL"
    TOOL = "TOOL"
    PROVIDER = "PROVIDER"
    EFFECT = "EFFECT"
    READBACK = "READBACK"
    PROOF = "PROOF"


FORBIDDEN_ATTRIBUTE_TOKENS = (
    "password",
    "private_key",
    "access_token",
    "refresh_token",
    "secret_value",
    "api_key_value",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sanitize_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in attributes.items():
        normalized = str(key).lower().replace("-", "_")
        if any(token in normalized for token in FORBIDDEN_ATTRIBUTE_TOKENS):
            if normalized.endswith(("_reference", "_ref", "_present")):
                sanitized[str(key)] = value
                continue
            raise ValueError(f"secret-bearing trace attribute forbidden: {key}")
        sanitized[str(key)] = value
    return sanitized


@dataclass(frozen=True)
class TraceSpan:
    trace_id: str
    span_id: str
    kind: SpanKind
    name: str
    started_at_ns: int
    ended_at_ns: int
    status: str
    parent_span_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    span_sha256: str = ""

    @classmethod
    def build(
        cls,
        *,
        trace_id: str,
        kind: SpanKind | str,
        name: str,
        status: str,
        parent_span_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
        started_at_ns: int | None = None,
        ended_at_ns: int | None = None,
        span_id: str | None = None,
    ) -> "TraceSpan":
        kind_value = kind if isinstance(kind, SpanKind) else SpanKind(str(kind))
        if not trace_id.strip() or not name.strip() or not status.strip():
            raise ValueError("trace_id, name and status are required")
        start = int(started_at_ns if started_at_ns is not None else time.time_ns())
        end = int(ended_at_ns if ended_at_ns is not None else start)
        if end < start:
            raise ValueError("trace span end precedes start")
        attrs = _sanitize_attributes(attributes or {})
        sid = span_id or uuid.uuid4().hex[:16]
        body = {
            "trace_id": trace_id,
            "span_id": sid,
            "parent_span_id": parent_span_id,
            "kind": kind_value.value,
            "name": name,
            "started_at_ns": start,
            "ended_at_ns": end,
            "status": status,
            "attributes": attrs,
        }
        return cls(
            trace_id=trace_id,
            span_id=sid,
            parent_span_id=parent_span_id,
            kind=kind_value,
            name=name,
            started_at_ns=start,
            ended_at_ns=end,
            status=status,
            attributes=attrs,
            span_sha256=hashlib.sha256(_stable_json(body).encode("utf-8")).hexdigest(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "name": self.name,
            "started_at_ns": self.started_at_ns,
            "ended_at_ns": self.ended_at_ns,
            "status": self.status,
            "attributes": dict(self.attributes),
            "span_sha256": self.span_sha256,
        }


class TraceBuffer:
    """Provider-neutral trace projection compatible with an OTel export adapter."""

    def __init__(self, trace_id: str):
        if not trace_id.strip():
            raise ValueError("trace_id required")
        self.trace_id = trace_id
        self._spans: dict[str, TraceSpan] = {}

    def append(self, span: TraceSpan) -> None:
        if span.trace_id != self.trace_id:
            raise ValueError("span belongs to a different trace")
        if span.span_id in self._spans:
            if self._spans[span.span_id].span_sha256 != span.span_sha256:
                raise ValueError("span id collision")
            return
        if span.parent_span_id is not None and span.parent_span_id not in self._spans:
            raise ValueError("parent span must be present before child")
        self._spans[span.span_id] = span

    def receipt(self) -> dict[str, Any]:
        spans = [item.to_dict() for item in self._spans.values()]
        root = hashlib.sha256(_stable_json(spans).encode("utf-8")).hexdigest()
        return {
            "schema": "SLOS_EXECUTION_TRACE_V1",
            "trace_id": self.trace_id,
            "span_count": len(spans),
            "spans": spans,
            "trace_sha256": root,
            "raw_secret_fields_allowed": False,
        }


__all__ = ["SpanKind", "TraceBuffer", "TraceSpan"]
