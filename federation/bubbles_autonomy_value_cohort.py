"""Proof-gated owner-value cohort court for Bubbles digital-twin convergence.

The court does not invent a new route/value optimizer and it stores no owner data.
It consumes already-observed mission telemetry and compares matched baseline versus
Bubbles-assisted mission pairs. The output is a bounded empirical-value candidate
receipt only; it does not prove provider runtime, background execution, AGI, or
sustained owner value by source presence or unit tests.

The court is intentionally conservative:
* task/oracle identity must match inside each pair;
* every observation requires proof references;
* incomplete or duplicate pairs fail closed;
* accepted-outcome quality may not regress;
* owner intervention/clarification/correction burden may not hide pair regressions;
* a positive creator-time delta is required for value-candidate status;
* no provider/external effect is authorized by the receipt.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from statistics import median
from typing import Iterable


BASELINE = "BASELINE"
BUBBLES = "BUBBLES"
OBSERVED_REAL_MISSION = "OBSERVED_REAL_MISSION"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonnegative(value: float, label: str) -> float:
    number = float(value)
    if number < 0.0:
        raise ValueError(f"{label}_NON_NEGATIVE_REQUIRED")
    return number


@dataclass(frozen=True, slots=True)
class MissionValueObservation:
    pair_id: str
    variant: str
    task_signature: str
    oracle_id: str
    accepted: bool
    cycle_time_seconds: float
    owner_intervention_seconds: float
    clarification_count: int
    correction_count: int
    observed_at: str
    proof_refs: tuple[str, ...]
    evidence_class: str = OBSERVED_REAL_MISSION

    def validate(self) -> "MissionValueObservation":
        if not self.pair_id.strip():
            raise ValueError("COHORT_PAIR_ID_REQUIRED")
        if self.variant not in {BASELINE, BUBBLES}:
            raise ValueError("COHORT_VARIANT_INVALID")
        if not self.task_signature.strip() or not self.oracle_id.strip():
            raise ValueError("COHORT_TASK_ORACLE_IDENTITY_REQUIRED")
        if not self.observed_at.strip():
            raise ValueError("COHORT_OBSERVED_AT_REQUIRED")
        _nonnegative(self.cycle_time_seconds, "COHORT_CYCLE_TIME")
        _nonnegative(self.owner_intervention_seconds, "COHORT_OWNER_INTERVENTION")
        if int(self.clarification_count) < 0 or int(self.correction_count) < 0:
            raise ValueError("COHORT_BURDEN_COUNTS_NON_NEGATIVE_REQUIRED")
        refs = tuple(sorted({str(item).strip() for item in self.proof_refs if str(item).strip()}))
        if not refs:
            raise ValueError("COHORT_PROOF_REFS_REQUIRED")
        if not self.evidence_class.strip():
            raise ValueError("COHORT_EVIDENCE_CLASS_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class AutonomyValuePolicy:
    min_pairs: int = 10
    min_candidate_acceptance_rate: float = 0.90
    max_acceptance_rate_regression: float = 0.0
    max_pair_burden_regressions: int = 0
    require_positive_creator_time_recovered: bool = True
    max_median_cycle_time_regression_ratio: float | None = None

    def validate(self) -> "AutonomyValuePolicy":
        if int(self.min_pairs) <= 0:
            raise ValueError("COHORT_MIN_PAIRS_INVALID")
        if not 0.0 <= float(self.min_candidate_acceptance_rate) <= 1.0:
            raise ValueError("COHORT_ACCEPTANCE_THRESHOLD_INVALID")
        if not 0.0 <= float(self.max_acceptance_rate_regression) <= 1.0:
            raise ValueError("COHORT_ACCEPTANCE_REGRESSION_INVALID")
        if int(self.max_pair_burden_regressions) < 0:
            raise ValueError("COHORT_PAIR_REGRESSION_LIMIT_INVALID")
        if self.max_median_cycle_time_regression_ratio is not None and float(
            self.max_median_cycle_time_regression_ratio
        ) < 0.0:
            raise ValueError("COHORT_CYCLE_TIME_REGRESSION_LIMIT_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class AutonomyValueReceipt:
    state: str
    promotion_eligible: bool
    pair_count: int
    baseline_acceptance_rate: float
    candidate_acceptance_rate: float
    creator_time_recovered_seconds: float
    median_owner_intervention_delta_seconds: float
    median_clarification_delta: float
    median_correction_delta: float
    median_cycle_time_delta_seconds: float
    burden_regression_pair_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    all_observations_real_mission_class: bool
    provider_effect_authorized: bool = False
    external_effect_authorized: bool = False
    truth_boundary: str = (
        "AUTONOMY_VALUE_CANDIDATE requires matched proof-referenced mission observations and bounded non-regression gates only. "
        "Source/tests do not prove sustained owner value, provider-hosted runtime, background execution, private-memory ingestion, AGI, or external effects."
    )
    receipt_sha256: str = ""

    def canonical_mapping(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("receipt_sha256", None)
        return payload


class BubblesAutonomyValueCourt:
    """Compare matched baseline/Bubbles mission observations without creating effects."""

    def evaluate(
        self,
        observations: Iterable[MissionValueObservation],
        *,
        policy: AutonomyValuePolicy | None = None,
    ) -> AutonomyValueReceipt:
        policy = (policy or AutonomyValuePolicy()).validate()
        records = tuple(item.validate() for item in observations)
        if not records:
            return self._receipt(
                state="HELD_NO_OBSERVATIONS",
                promotion_eligible=False,
                pair_count=0,
                blockers=("OBSERVED_MISSION_COHORT_REQUIRED",),
            )

        by_pair: dict[str, dict[str, MissionValueObservation]] = {}
        duplicate_keys: set[str] = set()
        refs: set[str] = set()
        all_real = True
        for item in records:
            refs.update(str(ref).strip() for ref in item.proof_refs if str(ref).strip())
            all_real = all_real and item.evidence_class == OBSERVED_REAL_MISSION
            variants = by_pair.setdefault(item.pair_id, {})
            if item.variant in variants:
                duplicate_keys.add(f"{item.pair_id}:{item.variant}")
                continue
            variants[item.variant] = item

        blockers: set[str] = set()
        if duplicate_keys:
            blockers.add("DUPLICATE_PAIR_VARIANT")

        matched: list[tuple[MissionValueObservation, MissionValueObservation]] = []
        for pair_id, variants in sorted(by_pair.items()):
            if set(variants) != {BASELINE, BUBBLES}:
                blockers.add("INCOMPLETE_BASELINE_CANDIDATE_PAIR")
                continue
            baseline = variants[BASELINE]
            candidate = variants[BUBBLES]
            if baseline.task_signature != candidate.task_signature:
                blockers.add("TASK_SIGNATURE_MISMATCH")
                continue
            if baseline.oracle_id != candidate.oracle_id:
                blockers.add("ORACLE_ID_MISMATCH")
                continue
            matched.append((baseline, candidate))

        pair_count = len(matched)
        if pair_count < int(policy.min_pairs):
            blockers.add("MINIMUM_OBSERVED_PAIR_COUNT_NOT_MET")

        if not matched:
            return self._receipt(
                state="HELD_INCOMPLETE_COMPARABILITY",
                promotion_eligible=False,
                pair_count=0,
                blockers=tuple(sorted(blockers or {"NO_COMPARABLE_PAIRS"})),
                evidence_refs=tuple(sorted(refs)),
                all_observations_real_mission_class=all_real,
            )

        baseline_acceptance = sum(1 for baseline, _ in matched if baseline.accepted) / pair_count
        candidate_acceptance = sum(1 for _, candidate in matched if candidate.accepted) / pair_count
        if candidate_acceptance < float(policy.min_candidate_acceptance_rate):
            blockers.add("CANDIDATE_ACCEPTANCE_RATE_BELOW_THRESHOLD")
        if baseline_acceptance - candidate_acceptance > float(policy.max_acceptance_rate_regression):
            blockers.add("ACCEPTED_OUTCOME_QUALITY_REGRESSION")

        intervention_deltas: list[float] = []
        clarification_deltas: list[float] = []
        correction_deltas: list[float] = []
        cycle_deltas: list[float] = []
        burden_regressions: list[str] = []
        creator_time_recovered = 0.0
        for baseline, candidate in matched:
            intervention_delta = float(baseline.owner_intervention_seconds) - float(
                candidate.owner_intervention_seconds
            )
            clarification_delta = float(baseline.clarification_count) - float(candidate.clarification_count)
            correction_delta = float(baseline.correction_count) - float(candidate.correction_count)
            cycle_delta = float(baseline.cycle_time_seconds) - float(candidate.cycle_time_seconds)
            intervention_deltas.append(intervention_delta)
            clarification_deltas.append(clarification_delta)
            correction_deltas.append(correction_delta)
            cycle_deltas.append(cycle_delta)
            creator_time_recovered += intervention_delta
            if (
                candidate.owner_intervention_seconds > baseline.owner_intervention_seconds
                or candidate.clarification_count > baseline.clarification_count
                or candidate.correction_count > baseline.correction_count
            ):
                burden_regressions.append(baseline.pair_id)

        if len(burden_regressions) > int(policy.max_pair_burden_regressions):
            blockers.add("PAIR_LEVEL_OWNER_BURDEN_REGRESSION")
        if policy.require_positive_creator_time_recovered and creator_time_recovered <= 0.0:
            blockers.add("POSITIVE_CREATOR_TIME_RECOVERY_NOT_PROVEN")

        baseline_cycle_median = median(float(b.cycle_time_seconds) for b, _ in matched)
        candidate_cycle_median = median(float(c.cycle_time_seconds) for _, c in matched)
        if policy.max_median_cycle_time_regression_ratio is not None:
            allowed = baseline_cycle_median * (
                1.0 + float(policy.max_median_cycle_time_regression_ratio)
            )
            if candidate_cycle_median > allowed:
                blockers.add("MEDIAN_CYCLE_TIME_REGRESSION")

        if blockers:
            if any(
                item in blockers
                for item in {
                    "DUPLICATE_PAIR_VARIANT",
                    "INCOMPLETE_BASELINE_CANDIDATE_PAIR",
                    "TASK_SIGNATURE_MISMATCH",
                    "ORACLE_ID_MISMATCH",
                    "MINIMUM_OBSERVED_PAIR_COUNT_NOT_MET",
                }
            ):
                state = "HELD_INCOMPLETE_EMPIRICAL_COHORT"
            elif any(
                item in blockers
                for item in {
                    "CANDIDATE_ACCEPTANCE_RATE_BELOW_THRESHOLD",
                    "ACCEPTED_OUTCOME_QUALITY_REGRESSION",
                }
            ):
                state = "HELD_ACCEPTED_OUTCOME_REGRESSION"
            else:
                state = "HELD_AUTONOMY_VALUE_REGRESSION"
            eligible = False
        elif not all_real:
            state = "DETERMINISTIC_COHORT_LOGIC_ONLY"
            eligible = False
        else:
            state = "AUTONOMY_VALUE_CANDIDATE"
            eligible = True

        return self._receipt(
            state=state,
            promotion_eligible=eligible,
            pair_count=pair_count,
            baseline_acceptance_rate=baseline_acceptance,
            candidate_acceptance_rate=candidate_acceptance,
            creator_time_recovered_seconds=creator_time_recovered,
            median_owner_intervention_delta_seconds=median(intervention_deltas),
            median_clarification_delta=median(clarification_deltas),
            median_correction_delta=median(correction_deltas),
            median_cycle_time_delta_seconds=median(cycle_deltas),
            burden_regression_pair_ids=tuple(sorted(set(burden_regressions))),
            blockers=tuple(sorted(blockers)),
            evidence_refs=tuple(sorted(refs)),
            all_observations_real_mission_class=all_real,
        )

    @staticmethod
    def _receipt(
        *,
        state: str,
        promotion_eligible: bool,
        pair_count: int,
        baseline_acceptance_rate: float = 0.0,
        candidate_acceptance_rate: float = 0.0,
        creator_time_recovered_seconds: float = 0.0,
        median_owner_intervention_delta_seconds: float = 0.0,
        median_clarification_delta: float = 0.0,
        median_correction_delta: float = 0.0,
        median_cycle_time_delta_seconds: float = 0.0,
        burden_regression_pair_ids: tuple[str, ...] = (),
        blockers: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
        all_observations_real_mission_class: bool = False,
    ) -> AutonomyValueReceipt:
        provisional = AutonomyValueReceipt(
            state=state,
            promotion_eligible=promotion_eligible,
            pair_count=pair_count,
            baseline_acceptance_rate=round(float(baseline_acceptance_rate), 9),
            candidate_acceptance_rate=round(float(candidate_acceptance_rate), 9),
            creator_time_recovered_seconds=round(float(creator_time_recovered_seconds), 6),
            median_owner_intervention_delta_seconds=round(
                float(median_owner_intervention_delta_seconds), 6
            ),
            median_clarification_delta=round(float(median_clarification_delta), 6),
            median_correction_delta=round(float(median_correction_delta), 6),
            median_cycle_time_delta_seconds=round(float(median_cycle_time_delta_seconds), 6),
            burden_regression_pair_ids=tuple(burden_regression_pair_ids),
            blockers=tuple(blockers),
            evidence_refs=tuple(evidence_refs),
            all_observations_real_mission_class=all_observations_real_mission_class,
        )
        return AutonomyValueReceipt(
            **{**provisional.canonical_mapping(), "receipt_sha256": _digest(provisional.canonical_mapping())}
        )


__all__ = [
    "AutonomyValuePolicy",
    "AutonomyValueReceipt",
    "BASELINE",
    "BUBBLES",
    "BubblesAutonomyValueCourt",
    "MissionValueObservation",
    "OBSERVED_REAL_MISSION",
]
