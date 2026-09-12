from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class FrontierState(str, Enum):
    RESEARCH = "RESEARCH"
    SHADOW = "SHADOW"
    HELD = "HELD"


@dataclass(frozen=True)
class InstitutionalFrontierCandidate:
    candidate_id: str
    concept: str
    reversible: bool
    authority_neutral: bool
    falsifiable: bool
    expected_owner_leverage_gain: float
    external_effect: bool = False


@dataclass(frozen=True)
class FrontierCandidateDecision:
    candidate_id: str
    state: FrontierState
    reason: str


def evaluate_frontier_candidates(candidates: Sequence[InstitutionalFrontierCandidate]) -> tuple[FrontierCandidateDecision, ...]:
    ids = [candidate.candidate_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate_id")
    decisions = []
    for candidate in candidates:
        if candidate.external_effect or not candidate.authority_neutral:
            state, reason = FrontierState.HELD, "AUTHORITY_OR_EFFECT_BOUNDARY"
        elif not candidate.falsifiable:
            state, reason = FrontierState.HELD, "FALSIFIABILITY_REQUIRED"
        elif candidate.reversible and candidate.expected_owner_leverage_gain > 0:
            state, reason = FrontierState.SHADOW, "REVERSIBLE_FRONTIER_CHALLENGER"
        else:
            state, reason = FrontierState.RESEARCH, "MORE_EVIDENCE_REQUIRED"
        decisions.append(FrontierCandidateDecision(candidate.candidate_id, state, reason))
    return tuple(sorted(decisions, key=lambda item: item.candidate_id))
