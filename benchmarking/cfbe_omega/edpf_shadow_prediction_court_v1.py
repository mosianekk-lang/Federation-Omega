from __future__ import annotations

"""Leakage-safe shadow prediction court for SOVARA EDPF v1.

The court evaluates predictions only after outcomes become observable. It is an
A1_INTERNAL measurement layer: it cannot dispatch work, alter live predictor
weights, authorize provider effects, or self-promote. Real historical evidence
and synthetic test fixtures remain explicitly separated.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Iterable, Sequence

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    Prediction,
    PredictionOutcome,
    PredictorProfile,
    update_predictor,
)

SCHEMA = "SOVARA_EDPF_SHADOW_PREDICTION_COURT_V1"
MIN_REAL_PAIRS = 30
MIN_HOLDOUT_PAIRS = 10
MIN_PREDICTORS = 3
MIN_INDEPENDENT_SOURCES = 2
MIN_BRIER_GAIN = 0.01


class EvidenceMode(str, Enum):
    REAL_MISSION = "REAL_MISSION"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"


@dataclass(frozen=True, slots=True)
class ShadowPredictionPair:
    pair_id: str
    mission_id: str
    source_head_sha: str
    predictor_source_fingerprint: str
    prediction_cutoff_epoch: int
    outcome_observed_epoch: int
    prediction: Prediction
    outcome: PredictionOutcome
    pre_outcome_evidence_refs: tuple[str, ...]
    outcome_proof_refs: tuple[str, ...]
    evidence_mode: EvidenceMode

    def validate(self) -> "ShadowPredictionPair":
        if not self.pair_id.strip() or not self.mission_id.strip():
            raise ValueError("EDPF_SHADOW_PAIR_IDENTITY_REQUIRED")
        if len(self.source_head_sha) != 40 or any(ch not in "0123456789abcdef" for ch in self.source_head_sha.lower()):
            raise ValueError("EDPF_SHADOW_SOURCE_HEAD_INVALID")
        if not self.predictor_source_fingerprint.strip():
            raise ValueError("EDPF_SHADOW_PREDICTOR_SOURCE_REQUIRED")
        if int(self.prediction_cutoff_epoch) >= int(self.outcome_observed_epoch):
            raise ValueError("EDPF_SHADOW_TEMPORAL_LEAKAGE")
        self.prediction.validate()
        self.outcome.validate()
        if self.prediction.prediction_id != self.outcome.prediction_id:
            raise ValueError("EDPF_SHADOW_PREDICTION_OUTCOME_MISMATCH")
        if not self.pre_outcome_evidence_refs:
            raise ValueError("EDPF_SHADOW_PRE_OUTCOME_EVIDENCE_REQUIRED")
        if not self.outcome_proof_refs:
            raise ValueError("EDPF_SHADOW_OUTCOME_PROOF_REQUIRED")
        if set(self.pre_outcome_evidence_refs) & set(self.outcome_proof_refs):
            raise ValueError("EDPF_SHADOW_OUTCOME_PROOF_LEAKED_INTO_PREDICTION")
        if not set(self.prediction.evidence_refs).issubset(set(self.pre_outcome_evidence_refs)):
            raise ValueError("EDPF_SHADOW_PREDICTION_EVIDENCE_NOT_PRE_OUTCOME")
        return self


@dataclass(frozen=True, slots=True)
class PredictorShadowScore:
    predictor_id: str
    domain: str
    source_fingerprints: tuple[str, ...]
    training_pairs: int
    holdout_pairs: int
    training_brier: float
    holdout_brier: float
    holdout_calibration_error: float
    holdout_accuracy: float
    trust_weight_after_training: float
    holdout_value_mae: float
    holdout_latency_mae: float
    holdout_owner_burden_mae: float


@dataclass(frozen=True, slots=True)
class ShadowPredictionCourtReceipt:
    schema: str
    source_head_sha: str
    evidence_mode: str
    pair_count: int
    training_count: int
    holdout_count: int
    predictor_count: int
    independent_source_count: int
    predictor_scores: tuple[PredictorShadowScore, ...]
    baseline_holdout_brier: float
    prediction_holdout_brier: float
    holdout_brier_gain: float
    best_predictors_by_domain: tuple[tuple[str, str], ...]
    decision: str
    blockers: tuple[str, ...]
    live_predictor_weights_changed: bool
    live_predictor_weight_change_authorized: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    owner_action_required: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + sha256(payload).hexdigest()


def _brier(prediction: Prediction, outcome: PredictionOutcome) -> float:
    observed = 1.0 if outcome.occurred else 0.0
    return (float(prediction.probability) - observed) ** 2


def _abs_error(prediction: Prediction, outcome: PredictionOutcome) -> float:
    observed = 1.0 if outcome.occurred else 0.0
    return abs(float(prediction.probability) - observed)


def _correct(prediction: Prediction, outcome: PredictionOutcome) -> int:
    return int((float(prediction.probability) >= 0.5) == bool(outcome.occurred))


def _mean(values: Iterable[float]) -> float:
    values = tuple(float(value) for value in values)
    return sum(values) / len(values) if values else 0.0


def _mae(pairs: Sequence[ShadowPredictionPair], predicted_attr: str, realised_attr: str) -> float:
    if not pairs:
        return 0.0
    values = [
        abs(float(getattr(pair.prediction, predicted_attr)) - float(getattr(pair.outcome, realised_attr)))
        for pair in pairs
    ]
    return round(_mean(values), 9)


def _profile_from_pairs(predictor_id: str, domain: str, pairs: Sequence[ShadowPredictionPair]) -> PredictorProfile:
    profile = PredictorProfile(predictor_id=predictor_id, domain=domain)
    for pair in sorted(pairs, key=lambda item: (item.prediction_cutoff_epoch, item.pair_id)):
        profile = update_predictor(profile, pair.prediction, pair.outcome)
    return profile


def _training_base_rates(pairs: Sequence[ShadowPredictionPair]) -> dict[str, float]:
    by_domain: dict[str, list[float]] = {}
    for pair in pairs:
        by_domain.setdefault(pair.prediction.domain, []).append(1.0 if pair.outcome.occurred else 0.0)
    return {domain: _mean(values) for domain, values in by_domain.items()}


def _baseline_brier(holdout: Sequence[ShadowPredictionPair], base_rates: dict[str, float]) -> float:
    if not holdout:
        return 0.0
    scores: list[float] = []
    for pair in holdout:
        probability = float(base_rates.get(pair.prediction.domain, 0.5))
        observed = 1.0 if pair.outcome.occurred else 0.0
        scores.append((probability - observed) ** 2)
    return round(_mean(scores), 9)


def _predictor_scores(
    training: Sequence[ShadowPredictionPair],
    holdout: Sequence[ShadowPredictionPair],
) -> tuple[PredictorShadowScore, ...]:
    identities = sorted({(pair.prediction.predictor_id, pair.prediction.domain) for pair in (*training, *holdout)})
    scores: list[PredictorShadowScore] = []
    for predictor_id, domain in identities:
        train = tuple(pair for pair in training if pair.prediction.predictor_id == predictor_id and pair.prediction.domain == domain)
        test = tuple(pair for pair in holdout if pair.prediction.predictor_id == predictor_id and pair.prediction.domain == domain)
        profile = _profile_from_pairs(predictor_id, domain, train)
        sources = tuple(sorted({pair.predictor_source_fingerprint for pair in (*train, *test)}))
        scores.append(
            PredictorShadowScore(
                predictor_id=predictor_id,
                domain=domain,
                source_fingerprints=sources,
                training_pairs=len(train),
                holdout_pairs=len(test),
                training_brier=round(_mean(_brier(pair.prediction, pair.outcome) for pair in train), 9),
                holdout_brier=round(_mean(_brier(pair.prediction, pair.outcome) for pair in test), 9),
                holdout_calibration_error=round(_mean(_abs_error(pair.prediction, pair.outcome) for pair in test), 9),
                holdout_accuracy=round(_mean(_correct(pair.prediction, pair.outcome) for pair in test), 9),
                trust_weight_after_training=profile.trust_weight,
                holdout_value_mae=_mae(test, "expected_value", "realised_value"),
                holdout_latency_mae=_mae(test, "expected_latency", "realised_latency"),
                holdout_owner_burden_mae=_mae(test, "expected_owner_burden", "realised_owner_burden"),
            )
        )
    return tuple(scores)


def evaluate_shadow_prediction_court(
    pairs: Sequence[ShadowPredictionPair],
    *,
    holdout_size: int = MIN_HOLDOUT_PAIRS,
) -> ShadowPredictionCourtReceipt:
    if not pairs:
        raise ValueError("EDPF_SHADOW_PAIR_REQUIRED")
    if len({pair.pair_id for pair in pairs}) != len(pairs):
        raise ValueError("EDPF_SHADOW_PAIR_IDS_MUST_BE_UNIQUE")
    validated = tuple(pair.validate() for pair in pairs)
    source_heads = {pair.source_head_sha for pair in validated}
    if len(source_heads) != 1:
        raise ValueError("EDPF_SHADOW_SOURCE_HEAD_MISMATCH")
    evidence_modes = {pair.evidence_mode for pair in validated}
    if len(evidence_modes) != 1:
        raise ValueError("EDPF_SHADOW_EVIDENCE_MODE_MIXED")
    if holdout_size < 1 or holdout_size >= len(validated):
        raise ValueError("EDPF_SHADOW_HOLDOUT_BOUND_INVALID")

    ordered = tuple(sorted(validated, key=lambda item: (item.prediction_cutoff_epoch, item.pair_id)))
    training, holdout = ordered[:-holdout_size], ordered[-holdout_size:]
    if training and max(item.prediction_cutoff_epoch for item in training) >= min(item.prediction_cutoff_epoch for item in holdout):
        raise ValueError("EDPF_SHADOW_CHRONOLOGICAL_SPLIT_INVALID")

    scores = _predictor_scores(training, holdout)
    predictor_ids = {pair.prediction.predictor_id for pair in ordered}
    independent_sources = {pair.predictor_source_fingerprint for pair in ordered}
    base_rates = _training_base_rates(training)
    baseline_brier = _baseline_brier(holdout, base_rates)
    prediction_brier = round(_mean(_brier(pair.prediction, pair.outcome) for pair in holdout), 9)
    brier_gain = round(baseline_brier - prediction_brier, 9)

    best_by_domain: list[tuple[str, str]] = []
    for domain in sorted({score.domain for score in scores}):
        eligible = [score for score in scores if score.domain == domain and score.holdout_pairs > 0]
        if eligible:
            best = sorted(eligible, key=lambda item: (item.holdout_brier, -item.holdout_accuracy, item.predictor_id))[0]
            best_by_domain.append((domain, best.predictor_id))

    blockers: list[str] = []
    mode = next(iter(evidence_modes))
    if mode is not EvidenceMode.REAL_MISSION:
        blockers.append("REAL_MISSION_EVIDENCE_REQUIRED_FOR_EMPIRICAL_PROMOTION")
    if len(ordered) < MIN_REAL_PAIRS:
        blockers.append("MINIMUM_REAL_SHADOW_PAIR_COHORT_REQUIRED")
    if len(holdout) < MIN_HOLDOUT_PAIRS:
        blockers.append("MINIMUM_CHRONOLOGICAL_HOLDOUT_REQUIRED")
    if len(predictor_ids) < MIN_PREDICTORS:
        blockers.append("MINIMUM_PREDICTOR_DIVERSITY_REQUIRED")
    if len(independent_sources) < MIN_INDEPENDENT_SOURCES:
        blockers.append("MINIMUM_INDEPENDENT_SOURCE_DIVERSITY_REQUIRED")
    if brier_gain < MIN_BRIER_GAIN:
        blockers.append("HOLDOUT_BRIER_GAIN_BELOW_FLOOR")

    if mode is EvidenceMode.REAL_MISSION and not blockers:
        decision = "REAL_SHADOW_CALIBRATION_POSITIVE"
    elif mode is EvidenceMode.REAL_MISSION:
        decision = "REAL_SHADOW_CALIBRATION_NEGATIVE_OR_INSUFFICIENT"
    else:
        decision = "SOURCE_COURT_READY_AWAITING_REAL_COHORT"

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "source_head_sha": next(iter(source_heads)),
        "evidence_mode": mode.value,
        "pair_count": len(ordered),
        "training_count": len(training),
        "holdout_count": len(holdout),
        "predictor_count": len(predictor_ids),
        "independent_source_count": len(independent_sources),
        "predictor_scores": scores,
        "baseline_holdout_brier": baseline_brier,
        "prediction_holdout_brier": prediction_brier,
        "holdout_brier_gain": brier_gain,
        "best_predictors_by_domain": tuple(best_by_domain),
        "decision": decision,
        "blockers": tuple(blockers),
        "live_predictor_weights_changed": False,
        "live_predictor_weight_change_authorized": False,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "stable_self_promotion_allowed": False,
        "owner_action_required": False,
    }
    body["receipt_sha256"] = _canonical_hash(body)
    return ShadowPredictionCourtReceipt(**body)
