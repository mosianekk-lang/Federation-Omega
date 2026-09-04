"""Generic claim-versus-fruit completion gate for MODISA missions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class OutcomeCriterion:
    criterion_id: str
    requirement_id: str
    description: str
    scope: str
    active: bool = True
    minimum_proofs: int = 1
    max_age_seconds: int | None = None


@dataclass(frozen=True)
class FruitObservation:
    criterion_id: str
    scope: str
    source_id: str
    proof_ids: tuple[str, ...]
    observed_at: datetime
    satisfied: bool
    contradiction: str | None = None


@dataclass(frozen=True)
class OutcomeVerdict:
    complete: bool
    satisfied_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]
    stale_ids: tuple[str, ...]
    contradicted_ids: tuple[str, ...]


class FruitGate:
    def evaluate(
        self,
        criteria: tuple[OutcomeCriterion, ...],
        observations: tuple[FruitObservation, ...],
        *,
        now: datetime | None = None,
    ) -> OutcomeVerdict:
        clock = now or datetime.now(UTC)
        by_criterion: dict[str, list[FruitObservation]] = {}
        for observation in observations:
            by_criterion.setdefault(observation.criterion_id, []).append(observation)

        satisfied: list[str] = []
        missing: list[str] = []
        stale: list[str] = []
        contradicted: list[str] = []
        for criterion in criteria:
            if not criterion.active:
                continue
            candidates = by_criterion.get(criterion.criterion_id, [])
            if any(item.contradiction or not item.satisfied for item in candidates):
                contradicted.append(criterion.criterion_id)
                continue
            scoped = [item for item in candidates if item.scope == criterion.scope and item.source_id]
            fresh: list[FruitObservation] = []
            for item in scoped:
                age = (clock - item.observed_at).total_seconds()
                if criterion.max_age_seconds is not None and age > criterion.max_age_seconds:
                    continue
                fresh.append(item)
            if scoped and not fresh:
                stale.append(criterion.criterion_id)
                continue
            if not fresh or max((len(item.proof_ids) for item in fresh), default=0) < criterion.minimum_proofs:
                missing.append(criterion.criterion_id)
                continue
            satisfied.append(criterion.criterion_id)
        complete = not missing and not stale and not contradicted
        return OutcomeVerdict(
            complete=complete,
            satisfied_ids=tuple(sorted(satisfied)),
            missing_ids=tuple(sorted(missing)),
            stale_ids=tuple(sorted(stale)),
            contradicted_ids=tuple(sorted(contradicted)),
        )
