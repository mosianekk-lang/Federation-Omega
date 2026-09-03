from __future__ import annotations

"""Measured owner-value optimizer for Bubbles Ω.

This module consumes only already-measured matched BASELINE/BUBBLES records.
It never invents owner time, cost, quality, or intervention metrics and never
grants provider authority.
"""

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from federation.sentinel_omega.owner_value_ingress import (
    BUBBLES,
    BASELINE,
    OwnerValueMissionRecord,
    OwnerValuePairCompiler,
)


SCHEMA = "BUBBLES-OMEGA-OWNER-VALUE-OPTIMIZER-V1"


@dataclass(frozen=True, slots=True)
class OwnerValueDecision:
    schema: str
    state: str
    measured_pair_count: int
    minimum_pairs: int
    score: float | None
    owner_minutes_saved: float
    intervention_reduction: int
    clarification_reduction: int
    correction_reduction: int
    verified_output_ratio_delta: float
    elapsed_seconds_delta: float
    champion: str
    proof_refs: tuple[str, ...]
    provider_effect_authorized: bool = False
    market_superiority_proven: bool = False
    owner_value_proven: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof_refs"] = list(self.proof_refs)
        payload["truth_boundary"] = {
            "owner_value_metrics_invented": False,
            "champion_grants_provider_authority": False,
            "champion_is_global_market_superiority": False,
        }
        return payload


class OwnerValueOptimizer:
    def __init__(self, *, minimum_pairs: int = 10) -> None:
        if minimum_pairs <= 0:
            raise ValueError("OWNER_VALUE_MINIMUM_PAIRS_POSITIVE_REQUIRED")
        self.minimum_pairs = int(minimum_pairs)

    @staticmethod
    def _group(records: Sequence[OwnerValueMissionRecord]) -> dict[str, list[OwnerValueMissionRecord]]:
        grouped: dict[str, list[OwnerValueMissionRecord]] = {}
        for record in records:
            record.validate()
            grouped.setdefault(record.pair_id, []).append(record)
        return grouped

    def evaluate(self, records: Sequence[OwnerValueMissionRecord]) -> OwnerValueDecision:
        pairs = []
        proof_refs: set[str] = set()
        for pair_id, items in sorted(self._group(records).items()):
            if len(items) != 2 or {item.variant for item in items} != {BASELINE, BUBBLES}:
                continue
            try:
                pair = OwnerValuePairCompiler.compile(items[0], items[1])
            except ValueError:
                continue
            pairs.append(pair)
            proof_refs.update(pair.proof_refs)

        if len(pairs) < self.minimum_pairs:
            return OwnerValueDecision(
                schema=SCHEMA,
                state="DATA_GATED",
                measured_pair_count=len(pairs),
                minimum_pairs=self.minimum_pairs,
                score=None,
                owner_minutes_saved=0.0,
                intervention_reduction=0,
                clarification_reduction=0,
                correction_reduction=0,
                verified_output_ratio_delta=0.0,
                elapsed_seconds_delta=0.0,
                champion="UNDETERMINED",
                proof_refs=tuple(sorted(proof_refs)),
                owner_value_proven=False,
                reason="INSUFFICIENT_MATCHED_MEASURED_OWNER_VALUE_COHORT",
            )

        owner_minutes_saved = sum(
            item.baseline_owner_minutes - item.candidate_owner_minutes for item in pairs
        )
        intervention_reduction = sum(
            item.baseline_owner_interventions - item.candidate_owner_interventions for item in pairs
        )
        clarification_reduction = sum(
            item.baseline_clarification_count - item.candidate_clarification_count for item in pairs
        )
        correction_reduction = sum(
            item.baseline_correction_count - item.candidate_correction_count for item in pairs
        )
        verified_delta = sum(
            item.candidate_verified_output_ratio - item.baseline_verified_output_ratio for item in pairs
        ) / len(pairs)
        elapsed_delta = sum(
            item.baseline_elapsed_seconds - item.candidate_elapsed_seconds for item in pairs
        )

        baseline_owner_minutes = sum(item.baseline_owner_minutes for item in pairs)
        time_ratio = owner_minutes_saved / baseline_owner_minutes if baseline_owner_minutes > 0 else 0.0
        intervention_base = sum(item.baseline_owner_interventions for item in pairs)
        intervention_ratio = (
            intervention_reduction / intervention_base if intervention_base > 0 else 0.0
        )
        quality_delta = verified_delta
        elapsed_base = sum(item.baseline_elapsed_seconds for item in pairs)
        latency_ratio = elapsed_delta / elapsed_base if elapsed_base > 0 else 0.0

        score = (
            0.45 * time_ratio
            + 0.20 * intervention_ratio
            + 0.25 * quality_delta
            + 0.10 * latency_ratio
        )
        champion = "BUBBLES" if score > 0 else ("BASELINE" if score < 0 else "TIE")
        owner_value_proven = score > 0
        return OwnerValueDecision(
            schema=SCHEMA,
            state="MEASURED_COHORT_EVALUATED",
            measured_pair_count=len(pairs),
            minimum_pairs=self.minimum_pairs,
            score=round(score, 6),
            owner_minutes_saved=round(owner_minutes_saved, 6),
            intervention_reduction=intervention_reduction,
            clarification_reduction=clarification_reduction,
            correction_reduction=correction_reduction,
            verified_output_ratio_delta=round(verified_delta, 6),
            elapsed_seconds_delta=round(elapsed_delta, 6),
            champion=champion,
            proof_refs=tuple(sorted(proof_refs)),
            owner_value_proven=owner_value_proven,
            reason="MEASURED_MATCHED_COHORT_ONLY",
        )


__all__ = ["OwnerValueDecision", "OwnerValueOptimizer"]
