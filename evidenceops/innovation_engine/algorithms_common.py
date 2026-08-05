from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


AUTHORITY_CEILING = "A1_INTERNAL"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def sha256(value: Any) -> str:
    payload = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def number(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def unique_text(values: Iterable[Any]) -> list[str]:
    return sorted({text(value) for value in values if text(value)})


@dataclass(frozen=True)
class AlgorithmResult:
    algorithm_id: str
    name: str
    status: str
    maturity: str
    output: Mapping[str, Any]
    violations: tuple[str, ...] = ()
    metrics: Mapping[str, float] | None = None
    evidence_refs: tuple[str, ...] = ()
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False

    def as_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["receipt_sha256"] = sha256(body)
        return body


@dataclass(frozen=True)
class AlgorithmOpportunity:
    algorithm_id: str
    title: str
    problem_family: str
    score: float
    signal_count: int
    evidence_refs: tuple[str, ...]
    reason: str
    maturity: str = "SOURCE_BACKED_OPPORTUNITY"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
