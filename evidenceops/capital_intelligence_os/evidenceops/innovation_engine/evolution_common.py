from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

AUTHORITY_CEILING = "A1_INTERNAL"
FORBIDDEN_CONFIG_KEYS = {
    "authority_expansion", "trust_transfer", "send_authority",
    "legal_filing_authority", "payment_authority", "destructive_authority",
    "secret", "credential", "token", "access_token", "refresh_token",
    "api_key", "password", "private_key",
}

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)

def digest(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def clamp_metric(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"metric must be numeric: {value!r}") from None
    if result < 0.0 or result > 1.0:
        raise ValueError(f"metric must be between 0 and 1: {result}")
    return result

def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys

@dataclass(frozen=True)
class EvolutionDecision:
    algorithm_id: str
    candidate_id: str
    decision: str
    baseline_version: str
    candidate_version: str
    baseline_score: float
    candidate_score: float
    gain: float
    hard_regressions: tuple[str, ...]
    reasons: tuple[str, ...]
    promoted: bool
    rollback_version: str
    receipt_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
