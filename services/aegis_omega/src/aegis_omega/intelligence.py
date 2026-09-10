from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

@dataclass(frozen=True)
class IntelRecord:
    source: str
    indicator_type: str
    value_digest: str
    confidence: float
    observed_at: str


def normalize_indicator(source: str, indicator_type: str, value: str, confidence: float) -> IntelRecord:
    """Store a digest by default; callers can keep raw indicators in access-controlled evidence storage."""
    return IntelRecord(
        source=source.strip().lower(),
        indicator_type=indicator_type.strip().lower(),
        value_digest=hashlib.sha256(value.encode("utf-8")).hexdigest(),
        confidence=max(0.0, min(1.0, confidence)),
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
