"""Secret-safe audit serialization."""

from __future__ import annotations

import re
from typing import Any

KEY_PATTERN = re.compile(r"(token|secret|password|api[_-]?key|authorization|cookie)", re.I)
VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.I),
]


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if KEY_PATTERN.search(str(key)) else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        for pattern in VALUE_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
    return value
