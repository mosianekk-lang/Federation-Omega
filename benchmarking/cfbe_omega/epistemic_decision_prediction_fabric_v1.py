from __future__ import annotations

"""SOVARA/CFBE Epistemic Decision & Prediction Fabric v1.

This module is an A1_INTERNAL composition layer. It does not create a new world
model, causal engine, scheduler, provider executor, memory root, or authority
plane. It binds already-available evidence, challenger proposals, predictions,
uncertainty and later outcomes into deterministic epistemic receipts.

Authority boundary:
- proposals and predictions are advisory;
- provider/effect authority is always false here;
- canonical truth is never promoted from model consensus;
- provider-native readback and SOL/SOVARA admission remain external gates.
"""

from dataclasses import asdict, dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Iterable, Mapping, Sequence

SCHEMA = "SOVARA_EDPF_V1"
MAX_UNCERTAINTY_FOR_DIRECT_DECISION = 0.35
INDEPENDENT_CHALLENGER_TRIGGER = 0.45
MIN_DECISION_SENSITIVITY = 0.05


class ClaimKind(str, Enum):
    FACT = "FACT"
    HYPOTHESIS = "HYPOTHESIS"
    INFERENCE = "INFERENCE"
    PREDICTION = "PREDICTION"


class EvidenceClass(str, Enum):
    PROVIDER_NATIVE = "PROVIDER_NATIVE"
    PRIMARY = "PRIMARY"
    AUTHENTICATED_DERIVATIVE = "AUTHENTICATED_DERIVATIVE"
    TEST = "TEST"
    MODEL = "MODEL"
    SYNTHETIC = "SYNTHETIC"


class DecisionState(str, Enum):
    DECIDE = "DECIDE"
    SEEK_EVIDENCE = "SEEK_EVIDENCE"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    evidence_class: EvidenceClass
    source_fingerprint: str
    freshness: float
    reliability: float
    supports: float

    def validate(self) -> "EvidenceRef":
        if not self.evidence_id.strip() or not self.source_fingerprint.strip():
            raise ValueError("EDPF_EVIDENCE_IDENTITY_REQUIRED")
        for name in ("freshness", "reliability"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_{name.upper()}_OUT_OF_RANGE")
        if not -1.0 <= float(self.supports) <= 1.0:
            raise ValueError("EDPF_SUPPORT_OUT_OF_RANGE")
        return self


@dataclass(frozen=True, slots=True)
class EpistemicClaim:
    claim_id: str
    kind: ClaimKind
    statement: str
    probability: float
    evidence_refs: tuple[EvidenceRef, ...]
    causal_parents: tuple[str, ...] = ()
    causal_children: tuple[str, ...] = ()
    contradiction_refs: tuple[str, ...] = ()
    expires_at_epoch: int | None = None

    def validate(self) -> "EpistemicClaim":
        if not self.claim_id.strip() or not self.statement.strip():
            raise ValueError("EDPF_CLAIM_IDENTITY_REQUIRED")
        if not 0.0 <= float(self.probability) <= 1.0:
            raise ValueError("EDPF_CLAIM_PROBABILITY_OUT_OF_RANGE")
        for evidence in self.evidence_refs:
            evidence.validate()
        return self

    def independent_source_count(self) -> int:
        return len({item.source_fingerprint for item in self.evidence_refs})

    def weighted_support(self) -> float:
        self.validate()
        if not self.evidence_refs:
            return 0.0
        weighted = [item.supports * item.reliability * item.freshness for item in self.evidence_refs]
        return round(sum(weighted) / len(weighted), 9)


@dataclass(frozen=True, slots=True)
class PredictorProfile:
    predictor_id: str
    domain: str
    attempts: int = 0
    brier_sum: float = 0.0
    absolute_error_sum: float = 0.0
    resolved_correct: int = 0

    def validate(self) -> "PredictorProfile":
        if not self.predictor_id.strip() or not self.domain.strip():
            raise ValueError("EDPF_PREDICTOR_IDENTITY_REQUIRED")
        if self.attempts < 0 or self.resolved_correct < 0 or self.resolved_correct > self.attempts:
            raise ValueError("EDPF_PREDICTOR_COUNT_INVALID")
        if self.brier_sum < 0.0 or self.absolute_error_sum < 0.0:
            raise ValueError("EDPF_PREDICTOR_ERROR_INVALID")
        return self

    @property
    def calibration_error(self) -> float:
        return round(self.absolute_error_sum / self.attempts, 9) if self.attempts else 0.5

    @property
    def brier_score(self) -> float:
        return round(self.brier_sum / self.attempts, 9) if self.attempts else 0.25

    @property
    def empirical_accuracy(self) -> float:
        return round(self.resolved_correct / self.attempts, 9) if self.attempts else 0.5

    @property
    def trust_weight(self) -> float:
        if not self.attempts:
            return 0.5
        score = 0.45 * self.empirical_accuracy + 0.35 * (1.0 - min(1.0, self.calibration_error)) + 0.20 * (1.0 - min(1.0, self.brier_score))
        return round(max(0.0, min(1.0, score)), 9)


@dataclass(frozen=True, slots=True)
class Prediction:
    prediction_id: str
    predictor_id: str
    domain: str
    event: str
    probability: float
    expected_value: float
    expected_latency: float
    expected_owner_burden: float
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> "Prediction":
        if not self.prediction_id.strip() or not self.predictor_id.strip() or not self.domain.strip() or not self.event.strip():
            raise ValueError("EDPF_PREDICTION_IDENTITY_REQUIRED")
        for name in ("probability", "expected_latency", "expected_owner_burden"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_{name.upper()}_OUT_OF_RANGE")
        if not isfinite(float(self.expected_value)):
            raise ValueError("EDPF_EXPECTED_VALUE_NONFINITE")
        return self


@dataclass(frozen=True, slots=True)
class PredictionOutcome:
    prediction_id: str
    occurred: bool
    realised_value: float
    realised_latency: float
    realised_owner_burden: float
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "PredictionOutcome":
        if not self.prediction_id.strip():
            raise ValueError("EDPF_OUTCOME_IDENTITY_REQUIRED")
        if not isfinite(float(self.realised_value)):
            raise ValueError("EDPF_REALISED_VALUE_NONFINITE")
        for name in ("realised_latency", "realised_owner_burden"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_{name.upper()}_OUT_OF_RANGE")
        return self


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    candidate_id: str
    resolves_claim_ids: tuple[str, ...]
    decision_flip_probability: float
    uncertainty_reduction: float
    acquisition_cost: float
    acquisition_risk: float
    freshness_gain: float

    def validate(self) -> "EvidenceCandidate":
        if not self.candidate_id.strip() or not self.resolves_claim_ids:
            raise ValueError("EDPF_EVIDENCE_CANDIDATE_IDENTITY_REQUIRED")
        for name in ("decision_flip_probability", "uncertainty_reduction", "acquisition_cost", "acquisition_risk", "freshness_gain"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_{name.upper()}_OUT_OF_RANGE")
        return self

    def information_value(self) -> float:
        self.validate()
        gain = 0.45 * self.decision_flip_probability + 0.35 * self.uncertainty_reduction + 0.20 * self.freshness_gain
        burden = 0.65 * self.acquisition_cost + 0.35 * self.acquisition_risk
        return round(gain - 0.45 * burden, 9)


@dataclass(frozen=True, slots=True)
class DecisionOption:
    option_id: str
    expected_value: float
    success_probability: float
    reversibility: float
    information_gain: float
    cost: float
    latency: float
    owner_burden: float
    risk: float
    external_effect: bool = False

    def validate(self) -> "DecisionOption":
        if not self.option_id.strip() or not isfinite(float(self.expected_value)):
            raise ValueError("EDPF_OPTION_IDENTITY_OR_VALUE_INVALID")
        for name in ("success_probability", "reversibility", "information_gain", "cost", "latency", "owner_burden", "risk"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_{name.upper()}_OUT_OF_RANGE")
        return self

    def utility(self, uncertainty: float) -> float:
        self.validate()
        benefit = self.expected_value * self.success_probability + 0.12 * self.reversibility + 0.10 * self.information_gain
        burden = 0.12 * self.cost + 0.10 * self.latency + 0.12 * self.owner_burden + 0.22 * self.risk + 0.18 * uncertainty
        if self.external_effect:
            burden += 0.08
        return round(benefit - burden, 9)


@dataclass(frozen=True, slots=True)
class EpistemicDecisionReceipt:
    schema: str
    cycle_id: str
    source_version: str
    claim_ids: tuple[str, ...]
    ranked_option_ids: tuple[str, ...]
    option_scores: tuple[tuple[str, float], ...]
    state: DecisionState
    selected_option_id: str | None
    next_evidence_candidate_id: str | None
    uncertainty: float
    independent_challenger_required: bool
    independent_challenger_satisfied: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    reason_codes: tuple[str, ...]
    receipt_sha256: str


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    raw = value if isinstance(value, str) else _canonical_json(value)
    return sha256(raw.encode("utf-8")).hexdigest()


def aggregate_uncertainty(claims: Sequence[EpistemicClaim]) -> float:
    if not claims:
        return 1.0
    values: list[float] = []
    for claim in claims:
        claim.validate()
        probability_uncertainty = 1.0 - abs(2.0 * claim.probability - 1.0)
        contradiction_penalty = min(1.0, 0.15 * len(claim.contradiction_refs))
        source_penalty = 0.15 if claim.independent_source_count() < 2 else 0.0
        values.append(min(1.0, probability_uncertainty + contradiction_penalty + source_penalty))
    return round(sum(values) / len(values), 9)


def rank_evidence_candidates(candidates: Sequence[EvidenceCandidate]) -> tuple[tuple[str, float], ...]:
    ranked = [(item.candidate_id, item.information_value()) for item in candidates]
    return tuple(sorted(ranked, key=lambda row: (-row[1], row[0])))


def update_predictor(profile: PredictorProfile, prediction: Prediction, outcome: PredictionOutcome) -> PredictorProfile:
    profile.validate()
    prediction.validate()
    outcome.validate()
    if prediction.predictor_id != profile.predictor_id or prediction.domain != profile.domain:
        raise ValueError("EDPF_PREDICTOR_PROFILE_MISMATCH")
    if prediction.prediction_id != outcome.prediction_id:
        raise ValueError("EDPF_PREDICTION_OUTCOME_MISMATCH")
    observed = 1.0 if outcome.occurred else 0.0
    error = prediction.probability - observed
    correct = int((prediction.probability >= 0.5) == outcome.occurred)
    return replace(
        profile,
        attempts=profile.attempts + 1,
        brier_sum=profile.brier_sum + error * error,
        absolute_error_sum=profile.absolute_error_sum + abs(error),
        resolved_correct=profile.resolved_correct + correct,
    )


def predictor_allocation_weight(profile: PredictorProfile, *, relevance: float, independence: float, expected_information_gain: float, cost: float, latency: float) -> float:
    profile.validate()
    for value in (relevance, independence, expected_information_gain, cost, latency):
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError("EDPF_ALLOCATION_INPUT_OUT_OF_RANGE")
    score = 0.34 * profile.trust_weight + 0.24 * relevance + 0.18 * independence + 0.16 * expected_information_gain - 0.04 * cost - 0.04 * latency
    return round(max(0.0, min(1.0, score)), 9)


def decide(
    *,
    cycle_id: str,
    source_version: str,
    claims: Sequence[EpistemicClaim],
    options: Sequence[DecisionOption],
    evidence_candidates: Sequence[EvidenceCandidate] = (),
    proposer_source_fingerprints: Iterable[str] = (),
) -> EpistemicDecisionReceipt:
    if not cycle_id.strip() or not source_version.strip():
        raise ValueError("EDPF_CYCLE_IDENTITY_REQUIRED")
    if not options:
        raise ValueError("EDPF_OPTION_REQUIRED")

    uncertainty = aggregate_uncertainty(claims)
    option_scores = tuple(sorted(((item.option_id, item.utility(uncertainty)) for item in options), key=lambda row: (-row[1], row[0])))
    ranked_ids = tuple(item[0] for item in option_scores)
    independent_sources = {item for item in proposer_source_fingerprints if str(item).strip()}
    challenger_required = uncertainty >= INDEPENDENT_CHALLENGER_TRIGGER or any(item.external_effect for item in options)
    challenger_satisfied = len(independent_sources) >= 2

    evidence_ranked = rank_evidence_candidates(evidence_candidates)
    next_evidence = evidence_ranked[0][0] if evidence_ranked and evidence_ranked[0][1] >= MIN_DECISION_SENSITIVITY else None
    reasons: list[str] = []

    if challenger_required and not challenger_satisfied:
        state = DecisionState.HOLD
        selected = None
        reasons.append("INDEPENDENT_CHALLENGER_REQUIRED")
    elif uncertainty > MAX_UNCERTAINTY_FOR_DIRECT_DECISION and next_evidence is not None:
        state = DecisionState.SEEK_EVIDENCE
        selected = None
        reasons.append("DECISION_SENSITIVE_UNCERTAINTY")
    else:
        state = DecisionState.DECIDE
        selected = ranked_ids[0]
        reasons.append("ADVISORY_DECISION_READY")

    payload = {
        "schema": SCHEMA,
        "cycle_id": cycle_id,
        "source_version": source_version,
        "claim_ids": tuple(item.claim_id for item in claims),
        "ranked_option_ids": ranked_ids,
        "option_scores": option_scores,
        "state": state.value,
        "selected_option_id": selected,
        "next_evidence_candidate_id": next_evidence,
        "uncertainty": uncertainty,
        "independent_challenger_required": challenger_required,
        "independent_challenger_satisfied": challenger_satisfied,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "stable_self_promotion_allowed": False,
        "reason_codes": tuple(reasons),
    }
    return EpistemicDecisionReceipt(
        schema=SCHEMA,
        cycle_id=cycle_id,
        source_version=source_version,
        claim_ids=payload["claim_ids"],
        ranked_option_ids=ranked_ids,
        option_scores=option_scores,
        state=state,
        selected_option_id=selected,
        next_evidence_candidate_id=next_evidence,
        uncertainty=uncertainty,
        independent_challenger_required=challenger_required,
        independent_challenger_satisfied=challenger_satisfied,
        dispatch_authorized=False,
        external_effect_authorized=False,
        stable_self_promotion_allowed=False,
        reason_codes=tuple(reasons),
        receipt_sha256=_digest(payload),
    )


def receipt_dict(receipt: EpistemicDecisionReceipt) -> Mapping[str, object]:
    return asdict(receipt)
