from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .errors import IntegrityFailure

_REDACT_KEYS = re.compile(r"(?i)(secret|token|password|credential|authorization|key)")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _REDACT_KEYS.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return "[REDACTED_BYTES]"
    return value


def audit_hash(sequence: int, event: dict[str, Any], previous_hash: str) -> str:
    return digest_json({"sequence": sequence, "event": redact(event), "previous_hash": previous_hash})


def verify_chain(rows: list[dict[str, Any]]) -> None:
    previous = "0" * 64
    for row in rows:
        event = json.loads(row["event_json"])
        expected = audit_hash(int(row["sequence"]), event, previous)
        if row["previous_hash"] != previous or row["event_hash"] != expected:
            raise IntegrityFailure("audit chain verification failed")
        previous = row["event_hash"]
