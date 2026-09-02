from __future__ import annotations

"""Host-invoked forecast-opportunity compiler for SOVARA EDPF.

This layer removes a manual question-authoring bottleneck without creating a
scheduler, predictor, provider client, probability model, database, authority
plane, execution route, or second epistemic scoring model.

Canonical decision-sensitive information value belongs to EDPF
``EvidenceCandidate.information_value()``. This module only adds forecast-
specific admissibility: measurable outcome observability, prospective temporal
separation, semantic de-duplication, and a bounded question budget.

Important epistemic boundary: canonical evidence information value is NOT an
event forecast probability and must never be transformed into one.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    EvidenceCandidate,
    MIN_DECISION_SENSITIVITY,
)
from .edpf_prediction_request import PredictionQuestion

SCHEMA = "SOVARA_EDPF_FORECAST_OPPORTUNITY_COMPILER_V1_1"
SCORE_BASIS = "EDPF_EVIDENCE_CANDIDATE_INFORMATION_VALUE"
MAX_QUESTIONS = 5
DEFAULT_MIN_INFORMATION_VALUE = MIN_DECISION_SENSITIVITY
DEFAULT_MIN_OUTCOME_OBSERVABILITY = 0.50


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _unit(name: str, value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"EDPF_FORECAST_{name.upper()}_OUT_OF_RANGE")
    return value


@dataclass(frozen=True, slots=True)
class ForecastSignal:
    signal_id: str
    mission_id: str
    system_source_head_sha: str
    mission_snapshot_digest: str
    domain: str
    event: str
    outcome_criterion: str
    created_at: str
    prediction_deadline_at: str
    outcome_not_before_at: str
    outcome_deadline_at: str
    evidence_candidate: EvidenceCandidate
    outcome_observability: float
    evidence_refs: tuple[str, ...] = ()
    context: Mapping[str, Any] | None = None
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"

    def validate(self) -> "ForecastSignal":
        if not self.signal_id.strip():
            raise ValueError("EDPF_FORECAST_SIGNAL_ID_REQUIRED")
        self.evidence_candidate.validate()
        _unit("outcome_observability", self.outcome_observability)
        # Forecast questions must be tied to at least one decision-sensitive
        # claim already represented by the canonical EDPF evidence candidate.
        if not self.evidence_candidate.resolves_claim_ids:
            raise ValueError("EDPF_FORECAST_RESOLVED_CLAIM_REQUIRED")
        # Reuse the admitted request contract for source, chronology, context,
        # matter-scope and sensitivity validation. A temporary deterministic ID
        # is sufficient because the final request ID is compiled later.
        self.to_question(request_id="EDPF-VALIDATE-" + _digest(self.signal_id).split(":", 1)[1][:16].upper()).validate()
        return self

    def canonical_information_value(self) -> float:
        """Return EDPF's canonical evidence information value unchanged."""
        self.validate()
        return self.evidence_candidate.information_value()

    def semantic_key(self) -> tuple[str, str, str, str, str, str]:
        return (
            self.mission_id,
            self.domain,
            self.event.strip(),
            self.outcome_criterion.strip(),
            self.outcome_not_before_at,
            self.outcome_deadline_at,
        )

    def to_question(self, *, request_id: str) -> PredictionQuestion:
        candidate = self.evidence_candidate
        context = dict(self.context or {})
        context.update(
            {
                "edpf_forecast_signal_id": self.signal_id,
                "edpf_evidence_candidate_id": candidate.candidate_id,
                "edpf_resolves_claim_ids": tuple(candidate.resolves_claim_ids),
                "edpf_decision_flip_probability": float(candidate.decision_flip_probability),
                "edpf_uncertainty_reduction": float(candidate.uncertainty_reduction),
                "edpf_acquisition_cost": float(candidate.acquisition_cost),
                "edpf_acquisition_risk": float(candidate.acquisition_risk),
                "edpf_freshness_gain": float(candidate.freshness_gain),
                "edpf_canonical_information_value": float(candidate.information_value()),
                "edpf_information_value_basis": SCORE_BASIS,
                "outcome_observability": float(self.outcome_observability),
                "information_value_is_event_probability": False,
            }
        )
        return PredictionQuestion(
            request_id=request_id,
            mission_id=self.mission_id,
            system_source_head_sha=self.system_source_head_sha,
            mission_snapshot_digest=self.mission_snapshot_digest,
            domain=self.domain,
            event=self.event,
            outcome_criterion=self.outcome_criterion,
            created_at=self.created_at,
            prediction_deadline_at=self.prediction_deadline_at,
            outcome_not_before_at=self.outcome_not_before_at,
            outcome_deadline_at=self.outcome_deadline_at,
            evidence_refs=tuple(self.evidence_refs),
            context=context,
            matter_scope=self.matter_scope,
            sensitivity=self.sensitivity,
        )


@dataclass(frozen=True, slots=True)
class ForecastOpportunity:
    signal_id: str
    score: float
    score_basis: str
    outcome_observability: float
    request_id: str
    question: PredictionQuestion
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeldForecastSignal:
    signal_id: str
    score: float
    score_basis: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForecastOpportunitySet:
    schema: str
    candidate_count: int
    unique_candidate_count: int
    selected_count: int
    opportunities: tuple[ForecastOpportunity, ...]
    held: tuple[HeldForecastSignal, ...]
    score_basis: str
    local_information_value_model_present: bool
    opportunity_scores_are_forecast_probabilities: bool
    provider_call_authorized: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    live_predictor_weight_change_authorized: bool
    stable_self_promotion_allowed: bool
    receipt_sha256: str


def _request_id(signal: ForecastSignal) -> str:
    seed = {
        "signal_id": signal.signal_id,
        "evidence_candidate_id": signal.evidence_candidate.candidate_id,
        "mission_id": signal.mission_id,
        "source_head": signal.system_source_head_sha,
        "snapshot": signal.mission_snapshot_digest,
        "semantic_key": signal.semantic_key(),
    }
    return "EDPF-OPP-" + _digest(seed).split(":", 1)[1][:20].upper()


def _strength(signal: ForecastSignal) -> tuple[float, float, str]:
    return (signal.canonical_information_value(), float(signal.outcome_observability), signal.signal_id)


def compile_forecast_opportunities(
    signals: Sequence[ForecastSignal],
    *,
    max_questions: int = 3,
    min_information_value: float = DEFAULT_MIN_INFORMATION_VALUE,
    min_outcome_observability: float = DEFAULT_MIN_OUTCOME_OBSERVABILITY,
) -> ForecastOpportunitySet:
    """Compile a bounded set of measurable prospective forecast questions.

    Information-value ranking is delegated entirely to the canonical EDPF
    ``EvidenceCandidate``. Duplicate semantic questions collapse to the strongest
    canonical evidence candidate. This compiler never generates a probability
    and never dispatches a request.
    """
    if not signals:
        raise ValueError("EDPF_FORECAST_SIGNAL_REQUIRED")
    if not 1 <= int(max_questions) <= MAX_QUESTIONS:
        raise ValueError("EDPF_FORECAST_MAX_QUESTIONS_INVALID")
    information_floor = float(min_information_value)
    if not -1.0 <= information_floor <= 1.0:
        raise ValueError("EDPF_FORECAST_MIN_INFORMATION_VALUE_OUT_OF_RANGE")
    observability_floor = _unit("min_outcome_observability", min_outcome_observability)

    validated = tuple(signal.validate() for signal in signals)
    if len({signal.signal_id for signal in validated}) != len(validated):
        raise ValueError("EDPF_FORECAST_DUPLICATE_SIGNAL_ID")
    if len({signal.evidence_candidate.candidate_id for signal in validated}) != len(validated):
        raise ValueError("EDPF_FORECAST_DUPLICATE_EVIDENCE_CANDIDATE_ID")

    best_by_key: dict[tuple[str, str, str, str, str, str], ForecastSignal] = {}
    duplicates: list[ForecastSignal] = []
    for signal in validated:
        key = signal.semantic_key()
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = signal
            continue
        if _strength(signal) > _strength(current):
            duplicates.append(current)
            best_by_key[key] = signal
        else:
            duplicates.append(signal)

    unique = tuple(best_by_key.values())
    ranked = tuple(sorted(unique, key=lambda item: (-item.canonical_information_value(), -item.outcome_observability, item.signal_id)))
    eligible = tuple(
        item
        for item in ranked
        if item.canonical_information_value() >= information_floor
        and item.outcome_observability >= observability_floor
    )
    selected_signals = eligible[:max_questions]
    selected_ids = {item.signal_id for item in selected_signals}

    opportunities: list[ForecastOpportunity] = []
    for signal in selected_signals:
        request_id = _request_id(signal)
        question = signal.to_question(request_id=request_id)
        question.validate()
        opportunities.append(
            ForecastOpportunity(
                signal_id=signal.signal_id,
                score=signal.canonical_information_value(),
                score_basis=SCORE_BASIS,
                outcome_observability=float(signal.outcome_observability),
                request_id=request_id,
                question=question,
                reason_codes=(
                    "CANONICAL_EDPF_INFORMATION_VALUE_ADMITTED",
                    "MEASURABLE_OUTCOME_CONTRACT",
                    "PROSPECTIVE_WINDOW_SEPARATED",
                ),
            )
        )

    held: list[HeldForecastSignal] = []
    for signal in duplicates:
        held.append(
            HeldForecastSignal(
                signal.signal_id,
                signal.canonical_information_value(),
                SCORE_BASIS,
                ("SEMANTIC_DUPLICATE",),
            )
        )
    for signal in ranked:
        if signal.signal_id in selected_ids:
            continue
        score = signal.canonical_information_value()
        if signal.outcome_observability < observability_floor:
            reason = "OUTCOME_OBSERVABILITY_BELOW_FLOOR"
        elif score < information_floor:
            reason = "BELOW_CANONICAL_INFORMATION_VALUE_FLOOR"
        else:
            reason = "QUESTION_BUDGET_EXHAUSTED"
        held.append(HeldForecastSignal(signal.signal_id, score, SCORE_BASIS, (reason,)))

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "candidate_count": len(validated),
        "unique_candidate_count": len(unique),
        "selected_count": len(opportunities),
        "opportunities": tuple(opportunities),
        "held": tuple(sorted(held, key=lambda item: item.signal_id)),
        "score_basis": SCORE_BASIS,
        "local_information_value_model_present": False,
        "opportunity_scores_are_forecast_probabilities": False,
        "provider_call_authorized": False,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "live_predictor_weight_change_authorized": False,
        "stable_self_promotion_allowed": False,
    }
    body["receipt_sha256"] = _digest(body)
    return ForecastOpportunitySet(**body)


def receipt_dict(result: ForecastOpportunitySet) -> dict[str, Any]:
    return asdict(result)
