"""Integer-only deterministic capability scoring and bounded selection."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    BlockerCode,
    CapabilityStatus,
    Recommendation,
    RecommendationRole,
    enum_value,
)
from .errors import ContractError
from .privacy import require_code

USEFUL_SCORE = 5000


@dataclass(frozen=True, slots=True)
class CapabilityCandidate:
    capability_code: str
    status: CapabilityStatus
    confidence_bp: int
    freshness_seconds: int
    evidence_count: int
    compatible: bool
    blocker_code: BlockerCode = BlockerCode.NONE

    def __post_init__(self) -> None:
        require_code(self.capability_code, field="capability_code")
        object.__setattr__(self, "status", enum_value(CapabilityStatus, self.status, field="status"))
        object.__setattr__(self, "blocker_code", enum_value(BlockerCode, self.blocker_code, field="blocker_code"))
        for name, lower, upper in (
            ("confidence_bp", 0, 10000),
            ("freshness_seconds", 0, 86400),
            ("evidence_count", 0, 100),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
                raise ContractError(f"INVALID_CANDIDATE_FIELD:{name}")
        if not isinstance(self.compatible, bool):
            raise ContractError("COMPATIBLE_MUST_BE_BOOLEAN")


def score_candidate(candidate: CapabilityCandidate) -> int:
    if not candidate.compatible or candidate.status is CapabilityStatus.UNAVAILABLE:
        return 0
    status_bonus = 500 if candidate.status is CapabilityStatus.AVAILABLE else 0
    freshness_bonus = max(0, 1000 - min(candidate.freshness_seconds, 1000))
    evidence_bonus = min(candidate.evidence_count, 10) * 50
    return min(12000, candidate.confidence_bp + status_bonus + freshness_bonus + evidence_bonus)


def coalesce_candidates(candidates: tuple[CapabilityCandidate, ...]) -> tuple[CapabilityCandidate, ...]:
    selected: dict[str, CapabilityCandidate] = {}
    for candidate in candidates:
        prior = selected.get(candidate.capability_code)
        current_key = (score_candidate(candidate), candidate.status.value, candidate.blocker_code.value)
        prior_key = (
            score_candidate(prior), prior.status.value, prior.blocker_code.value
        ) if prior is not None else None
        if prior is None or current_key > prior_key:
            selected[candidate.capability_code] = candidate
    return tuple(selected[key] for key in sorted(selected))


def select_recommendations(candidates: tuple[CapabilityCandidate, ...]) -> tuple[Recommendation, ...]:
    unique = coalesce_candidates(candidates)
    useful = sorted(
        (
            (score_candidate(candidate), candidate)
            for candidate in unique
            if score_candidate(candidate) >= USEFUL_SCORE
        ),
        key=lambda pair: (-pair[0], pair[1].capability_code),
    )
    recommendations: list[Recommendation] = []
    for role, pair in zip(
        (RecommendationRole.PREFERRED, RecommendationRole.BACKUP),
        useful[:2],
        strict=False,
    ):
        score, candidate = pair
        recommendations.append(
            Recommendation(
                role=role,
                capability_code=candidate.capability_code,
                score=score,
                blocker_code=candidate.blocker_code,
            )
        )
    blockers = sorted(
        (
            candidate
            for candidate in unique
            if candidate.blocker_code is not BlockerCode.NONE
            and score_candidate(candidate) < USEFUL_SCORE
        ),
        key=lambda item: (item.blocker_code.value, item.capability_code),
    )
    if recommendations and blockers:
        blocked = blockers[0]
        recommendations.append(
            Recommendation(
                role=RecommendationRole.ESCALATION,
                capability_code=blocked.capability_code,
                score=0,
                blocker_code=blocked.blocker_code,
            )
        )
    return tuple(recommendations)
