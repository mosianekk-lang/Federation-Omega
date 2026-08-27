"""Provider-neutral tournament contracts for Quant Evidence Fabric v3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Candidate:
    provider: str
    job_id: str
    status: str
    strategy_id: str | None = None
    code_sha256: str | None = None
    review_score: float | None = None
    failure: str | None = None


def validate_tournament(candidates: Iterable[Candidate], expected_providers: set[str]) -> None:
    rows = tuple(candidates)
    providers = [c.provider for c in rows]
    if set(providers) != expected_providers:
        raise ValueError("provider set differs from tournament contract")
    if len(providers) != len(set(providers)):
        raise ValueError("duplicate provider identity")
    for candidate in rows:
        if candidate.status == "COMPLETED" and (not candidate.strategy_id or not candidate.code_sha256):
            raise ValueError(f"completed candidate {candidate.provider} lacks source identity")
        if candidate.status == "FAILED" and not candidate.failure:
            raise ValueError(f"failed candidate {candidate.provider} lacks failure evidence")


def eligible_for_backtest(candidate: Candidate) -> bool:
    return candidate.status == "COMPLETED" and bool(candidate.strategy_id and candidate.code_sha256)


def generation_score_is_not_performance_evidence(candidate: Candidate) -> bool:
    """Explicit invariant: an AI review score never admits a trading candidate."""
    return True
