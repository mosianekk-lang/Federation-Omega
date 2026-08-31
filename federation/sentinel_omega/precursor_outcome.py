from __future__ import annotations

"""Immutable prospective outcome accounting for Sentinel Ω precursor warnings.

This module evaluates later evidence against previously emitted heartbeat warnings.
It does not generate provider observations, execute repairs, infer counterfactual
prevention, or promote prediction accuracy from historical replay.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import statistics
from typing import Iterable, Sequence

from .heartbeat_precursor import CadenceState, HeartbeatCadenceAssessment

SCHEMA = "SENTINEL-OMEGA-PRECURSOR-OUTCOME-V1"
EXTERNAL_EFFECTS = False


def _time(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


class PredictionOutcome(StrEnum):
    ON_TIME_AFTER_WARNING = "ON_TIME_AFTER_WARNING"
    RECOVERED_AFTER_WARNING = "RECOVERED_AFTER_WARNING"
    MISSED_OR_STALE_CONFIRMED = "MISSED_OR_STALE_CONFIRMED"
    FALSE_POSITIVE_VERIFIED = "FALSE_POSITIVE_VERIFIED"
    CENSORED_INSUFFICIENT_FOLLOWUP = "CENSORED_INSUFFICIENT_FOLLOWUP"


@dataclass(frozen=True)
class PrecursorPrediction:
    prediction_id: str
    target_id: str
    model_schema: str
    source_sha: str
    predicted_state: CadenceState
    last_seen_at: str
    assessed_at: str
    expected_next_at: str
    watch_at: str
    precursor_at: str
    stale_at: str
    sample_count: int
    median_interval_seconds: float
    mad_seconds: float
    jitter_seconds: float
    recurrence_risk: bool
    proof_refs: tuple[str, ...]
    external_effect: bool = False

    @classmethod
    def from_assessment(
        cls,
        assessment: HeartbeatCadenceAssessment,
        *,
        prediction_id: str,
        model_schema: str,
        source_sha: str,
        sample_count: int,
        median_interval_seconds: float,
        mad_seconds: float,
        jitter_seconds: float,
        proof_refs: Iterable[str],
    ) -> "PrecursorPrediction":
        refs = tuple(sorted({str(x) for x in proof_refs if str(x)}))
        if not prediction_id.strip() or not source_sha.strip() or not model_schema.strip():
            raise ValueError("prediction identity, model schema and source SHA are required")
        if assessment.state == CadenceState.HEALTHY:
            raise ValueError("healthy assessments are not prospective warning predictions")
        if sample_count < 5:
            raise ValueError("prospective prediction requires at least five profile intervals")
        if not refs:
            raise ValueError("prediction requires proof_refs")
        return cls(
            prediction_id=prediction_id,
            target_id=assessment.target_id,
            model_schema=model_schema,
            source_sha=source_sha,
            predicted_state=assessment.state,
            last_seen_at=assessment.last_seen_at,
            assessed_at=assessment.assessed_at,
            expected_next_at=assessment.expected_next_at,
            watch_at=assessment.watch_at,
            precursor_at=assessment.precursor_at,
            stale_at=assessment.stale_at,
            sample_count=int(sample_count),
            median_interval_seconds=float(median_interval_seconds),
            mad_seconds=float(mad_seconds),
            jitter_seconds=float(jitter_seconds),
            recurrence_risk=assessment.recurrence_risk,
            proof_refs=refs,
        ).validate()

    def validate(self) -> "PrecursorPrediction":
        if self.predicted_state == CadenceState.HEALTHY:
            raise ValueError("prediction must represent WATCH, PRECURSOR or STALE")
        if self.sample_count < 5:
            raise ValueError("prediction sample_count must be at least five")
        if not self.proof_refs:
            raise ValueError("prediction requires proof_refs")
        ordered = tuple(_time(x) for x in (self.last_seen_at, self.expected_next_at, self.watch_at, self.precursor_at, self.stale_at))
        if not (ordered[0] <= ordered[1] <= ordered[2] <= ordered[3] <= ordered[4]):
            raise ValueError("prediction thresholds must be monotonic")
        if _time(self.assessed_at) < ordered[0]:
            raise ValueError("assessment cannot precede last seen heartbeat")
        return self


@dataclass(frozen=True)
class PrecursorOutcomeEvidence:
    observed_at: str
    proof_refs: tuple[str, ...]
    next_heartbeat_at: str | None = None
    stale_confirmed: bool = False
    intentional_pause_verified: bool = False
    false_positive_verified: bool = False
    repair_applied: bool = False
    owner_intervention_seconds: float | None = None
    external_effect: bool = False

    def validate(self) -> "PrecursorOutcomeEvidence":
        _time(self.observed_at)
        if self.next_heartbeat_at is not None:
            _time(self.next_heartbeat_at)
        if not self.proof_refs:
            raise ValueError("outcome evidence requires proof_refs")
        if self.intentional_pause_verified and self.false_positive_verified:
            raise ValueError("intentional pause and verified false positive are distinct outcomes")
        if self.owner_intervention_seconds is not None and self.owner_intervention_seconds < 0:
            raise ValueError("owner intervention cannot be negative")
        return self


@dataclass(frozen=True)
class ResolvedPrecursorOutcome:
    prediction_id: str
    target_id: str
    predicted_state: CadenceState
    outcome: PredictionOutcome
    resolved_at: str
    actual_heartbeat_at: str | None
    warning_lead_to_stale_seconds: float
    actual_delay_from_expected_seconds: float | None
    repair_applied: bool
    prevention_claim: bool
    owner_intervention_seconds: float | None
    proof_refs: tuple[str, ...]
    external_effect: bool = False


class PrecursorOutcomeResolver:
    """Resolve one immutable prediction using later, independently sourced evidence."""

    def resolve(
        self,
        prediction: PrecursorPrediction,
        evidence: PrecursorOutcomeEvidence,
    ) -> ResolvedPrecursorOutcome:
        prediction.validate()
        evidence.validate()
        assessed = _time(prediction.assessed_at)
        stale_at = _time(prediction.stale_at)
        expected = _time(prediction.expected_next_at)
        observed = _time(evidence.observed_at)
        if observed < assessed:
            raise ValueError("outcome evidence cannot precede prediction")

        heartbeat = _time(evidence.next_heartbeat_at) if evidence.next_heartbeat_at else None
        if heartbeat is not None and heartbeat < assessed:
            raise ValueError("next heartbeat cannot precede prediction")

        if evidence.intentional_pause_verified:
            outcome = PredictionOutcome.CENSORED_INSUFFICIENT_FOLLOWUP
        elif evidence.false_positive_verified:
            outcome = PredictionOutcome.FALSE_POSITIVE_VERIFIED
        elif evidence.stale_confirmed or (heartbeat is not None and heartbeat > stale_at):
            outcome = PredictionOutcome.MISSED_OR_STALE_CONFIRMED
        elif heartbeat is not None:
            precursor_at = _time(prediction.precursor_at)
            if prediction.predicted_state == CadenceState.WATCH and heartbeat <= precursor_at:
                outcome = PredictionOutcome.ON_TIME_AFTER_WARNING
            else:
                outcome = PredictionOutcome.RECOVERED_AFTER_WARNING
        else:
            outcome = PredictionOutcome.CENSORED_INSUFFICIENT_FOLLOWUP

        actual_delay = None if heartbeat is None else max(0.0, (heartbeat - expected).total_seconds())
        refs = tuple(sorted(set(prediction.proof_refs) | set(evidence.proof_refs)))
        return ResolvedPrecursorOutcome(
            prediction_id=prediction.prediction_id,
            target_id=prediction.target_id,
            predicted_state=prediction.predicted_state,
            outcome=outcome,
            resolved_at=evidence.observed_at,
            actual_heartbeat_at=evidence.next_heartbeat_at,
            warning_lead_to_stale_seconds=max(0.0, (stale_at - assessed).total_seconds()),
            actual_delay_from_expected_seconds=None if actual_delay is None else round(actual_delay, 6),
            repair_applied=evidence.repair_applied,
            prevention_claim=False,
            owner_intervention_seconds=evidence.owner_intervention_seconds,
            proof_refs=refs,
        )


@dataclass(frozen=True)
class PrecursorCohortMetrics:
    prediction_count: int
    resolved_non_censored_count: int
    censored_count: int
    stale_confirmed_count: int
    recovered_after_warning_count: int
    on_time_after_warning_count: int
    verified_false_positive_count: int
    stale_confirmation_rate: float | None
    verified_false_positive_rate: float | None
    median_warning_lead_seconds: float | None
    median_owner_intervention_seconds: float | None
    accuracy_claim_allowed: bool
    prevention_value_claim_allowed: bool = False
    external_effect: bool = False


class PrecursorCohortEvaluator:
    """Aggregate prospective outcomes without claiming causal prevention or value."""

    def __init__(self, *, minimum_accuracy_samples: int = 10) -> None:
        if minimum_accuracy_samples < 5:
            raise ValueError("minimum_accuracy_samples must be at least five")
        self.minimum_accuracy_samples = int(minimum_accuracy_samples)

    def evaluate(self, outcomes: Sequence[ResolvedPrecursorOutcome]) -> PrecursorCohortMetrics:
        ids = [x.prediction_id for x in outcomes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate prediction outcomes are not allowed")
        censored = [x for x in outcomes if x.outcome == PredictionOutcome.CENSORED_INSUFFICIENT_FOLLOWUP]
        resolved = [x for x in outcomes if x.outcome != PredictionOutcome.CENSORED_INSUFFICIENT_FOLLOWUP]
        stale = [x for x in resolved if x.outcome == PredictionOutcome.MISSED_OR_STALE_CONFIRMED]
        recovered = [x for x in resolved if x.outcome == PredictionOutcome.RECOVERED_AFTER_WARNING]
        on_time = [x for x in resolved if x.outcome == PredictionOutcome.ON_TIME_AFTER_WARNING]
        false_pos = [x for x in resolved if x.outcome == PredictionOutcome.FALSE_POSITIVE_VERIFIED]
        leads = [x.warning_lead_to_stale_seconds for x in resolved]
        owner = [x.owner_intervention_seconds for x in resolved if x.owner_intervention_seconds is not None]
        denominator = len(resolved)
        return PrecursorCohortMetrics(
            prediction_count=len(outcomes),
            resolved_non_censored_count=denominator,
            censored_count=len(censored),
            stale_confirmed_count=len(stale),
            recovered_after_warning_count=len(recovered),
            on_time_after_warning_count=len(on_time),
            verified_false_positive_count=len(false_pos),
            stale_confirmation_rate=None if denominator == 0 else round(len(stale) / denominator, 6),
            verified_false_positive_rate=None if denominator == 0 else round(len(false_pos) / denominator, 6),
            median_warning_lead_seconds=None if not leads else round(float(statistics.median(leads)), 6),
            median_owner_intervention_seconds=None if not owner else round(float(statistics.median(owner)), 6),
            accuracy_claim_allowed=denominator >= self.minimum_accuracy_samples,
            prevention_value_claim_allowed=False,
        )
