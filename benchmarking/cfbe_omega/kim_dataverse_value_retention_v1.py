from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class RetentionAction(str, Enum):
    RETAIN = "RETAIN"
    CHALLENGE = "CHALLENGE"
    ROLLBACK_CANDIDATE = "ROLLBACK_CANDIDATE"
    VALUE_HOLD = "VALUE_HOLD"


@dataclass(frozen=True)
class CapabilityValueWindow:
    capability_id: str
    observed_episodes: int
    verified_successes: int
    owner_value_pairs: int
    quality_regressions: int
    reliability_regressions: int
    owner_burden_regressions: int
    rollback_available: bool


@dataclass(frozen=True)
class RetentionDecision:
    capability_id: str
    action: RetentionAction
    value_proven: bool
    rollback_authorized: bool


def evaluate_value_retention(
    windows: Sequence[CapabilityValueWindow],
    *,
    minimum_episodes: int = 10,
    minimum_owner_value_pairs: int = 10,
) -> tuple[RetentionDecision, ...]:
    ids = [item.capability_id for item in windows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate capability_id")
    decisions = []
    for item in windows:
        counts = (
            item.observed_episodes,
            item.verified_successes,
            item.owner_value_pairs,
            item.quality_regressions,
            item.reliability_regressions,
            item.owner_burden_regressions,
        )
        if any(value < 0 for value in counts):
            raise ValueError("counts must be non-negative")
        if item.verified_successes > item.observed_episodes:
            raise ValueError("verified successes cannot exceed observed episodes")
        value_proven = (
            item.observed_episodes >= minimum_episodes
            and item.owner_value_pairs >= minimum_owner_value_pairs
            and item.verified_successes == item.observed_episodes
            and item.quality_regressions == 0
            and item.reliability_regressions == 0
            and item.owner_burden_regressions == 0
        )
        regressions = item.quality_regressions + item.reliability_regressions + item.owner_burden_regressions
        if value_proven:
            action = RetentionAction.RETAIN
        elif regressions and item.rollback_available:
            action = RetentionAction.ROLLBACK_CANDIDATE
        elif item.observed_episodes < minimum_episodes or item.owner_value_pairs < minimum_owner_value_pairs:
            action = RetentionAction.VALUE_HOLD
        else:
            action = RetentionAction.CHALLENGE
        decisions.append(RetentionDecision(item.capability_id, action, value_proven, False))
    return tuple(sorted(decisions, key=lambda item: item.capability_id))
