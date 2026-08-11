from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .algorithms import AUTHORITY_CEILING, sha256

@dataclass(frozen=True)
class FoundryCycleResult:
    cycle_id: str
    status: str
    algorithm_results: tuple[Mapping[str, Any], ...]
    opportunity_count: int
    innovation_delta: Mapping[str, Any]
    learning_delta: Mapping[str, Any]
    maturity: str
    proof: Mapping[str, Any]
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False

    def as_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["receipt_sha256"] = sha256(body)
        return body
