from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


_SENSITIVE_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "private" + "_" + "key",
    "api" + "_" + "key",
    "credential",
    "auth_material",
    "authorization",
    "cookie",
    "session_id",
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)[?&](?:token|secret|password|api[_-]?key|authorization)=[^&#\s]+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
_TRACEPARENT = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def canonical_utc(value: str) -> str:
    return parse_utc(value).isoformat().replace("+00:00", "Z")


def require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a JSON boolean")
    return value


def require_finite_number(value: Any, field: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a JSON number")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"{field} must be finite and >= {minimum}")
    return result


def require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return value


def ensure_absolute_uri(value: str, field: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme:
        raise ValueError(f"{field} must be an absolute URI")
    return value


def validate_traceparent(value: str) -> str:
    match = _TRACEPARENT.fullmatch(value)
    if not match:
        raise ValueError("invalid W3C traceparent")
    if match.group(1) == "0" * 32 or match.group(2) == "0" * 16:
        raise ValueError("trace identifiers cannot be all zeroes")
    return value


def new_traceparent(sampled: bool = True) -> str:
    flags = "01" if sampled else "00"
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-{flags}"


def reject_sensitive(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-JSON object key prohibited at {path}")
            normalized = str(key).lower().replace("-", "_")
            if any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS):
                raise ValueError(f"sensitive material field prohibited at {path}.{key}")
            reject_sensitive(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS):
            raise ValueError(f"sensitive material value prohibited at {path}")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite JSON number prohibited at {path}")
    elif value is not None and not isinstance(value, (bool, int, float)):
        raise ValueError(f"non-JSON value prohibited at {path}")


def require_nonempty(value: Any, field: str) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{field} required")
    return value
