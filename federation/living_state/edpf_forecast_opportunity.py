from __future__ import annotations

"""Host-invoked forecast-opportunity compiler for SOVARA EDPF.

This layer removes a manual question-authoring bottleneck without creating a
scheduler, predictor, provider client, probability model, database, authority
plane, or execution route. It ranks measurable mission uncertainties by their
expected decision value and compiles only the strongest opportunities into the
already-admitted :class:`PredictionQuestion` contract.

Important epistemic boundary: an opportunity score is NOT a forecast
probability and must never be transformed into one.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .edpf_prediction_request import PredictionQuestion

SCHEMA = "SOVARA_EDPF_FORECAST_OPPORTUNITY_COMPILER_V1"
MAX_QUESTIONS = 5
DEFAULT_MIN_SCORE = 0.20


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
    uncertainty: float
    decision_flip_probability: float
    decision_impact: float
    observability: float
    acquisition_cost: float
    owner_burden: float
    evidence_refs: tuple[str, ...] = ()
    context: Mapping[str, Any] | None = None
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"

    def validate(self) -> "ForecastSignal":
        if not self.signal_id.strip():
            raise ValueError("EDPF_FORECAST_SIGNAL_ID_REQUIRED")
        for name in (
            "uncertainty",
            "decision_flip_probability",
            "decision_impact",
            "observability",
            "acquisition_cost",
            "owner_burden",
        ):
            _unit(name, getattr(self, name))
        # Reuse the admitted request contract for source, chronology, context,
        # matter-scope and sensitivity validation. A temporary deterministic ID
        # is sufficient because the final request ID is compiled later.
        self.to_question(request_id="EDPF-VALIDATE-" + _digest(self.signal_id).split(":", 1)[1][:16].upper()).validate()
        return self

    def opportunity_score(self) -> float:
        """Rank decision-relevant uncertainty, not event probability."""
        self.validate()
        information_value = self.uncertainty * (
            0.40 * self.decision_flip_probability
            + 0.35 * self.decision_impact
            + 0.25 * self.observability
        )
        burden = 0.12 * self.acquisition_cost + 0.08 * self.owner_burden
        return round(max(0.0, min(1.0, information_value - burden)), 9)

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
        context = dict(self.context or {})
        context.update(
            {
                "edpf_forecast_signal_id": self.signal_id,
                "decision_sensitive_uncertainty": float(self.uncertainty),
                "decision_flip_probability": float(self.decision_flip_probability),
                "decision_impact": float(self.decision_impact),
                "outcome_observability": float(self.observability),
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
    request_id: str
    question: PredictionQuestion
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeldForecastSignal:
    signal_id: str
    score: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForecastOpportunitySet:
    schema: str
    candidate_count: int
    unique_candidate_count: int
    selected_count: int
    opportunities: tuple[ForecastOpportunity, ...]
    held: tuple[HeldForecastSignal, ...]
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
        "mission_id": signal.mission_id,
        "source_head": signal.system_source_head_sha,
        "snapshot": signal.mission_snapshot_digest,
        "semantic_key": signal.semantic_key(),
    }
    return "EDPF-OPP-" + _digest(seed).split(":", 1)[1][:20].upper()


def compile_forecast_opportunities(
    signals: Sequence[ForecastSignal],
    *,
    max_questions: int = 3,
    min_score: float = DEFAULT_MIN_SCORE,
) -> ForecastOpportunitySet:
    """Compile the smallest high-value set of measurable forecast questions.

    Duplicate semantic questions are collapsed to their highest-scoring signal.
    The compiler never generates a probability and never dispatches a request.
    """
    if not signals:
        raise ValueError("EDPF_FORECAST_SIGNAL_REQUIRED")
    if not 1 <= int(max_questions) <= MAX_QUESTIONS:
        raise ValueError("EDPF_FORECAST_MAX_QUESTIONS_INVALID")
    threshold = _unit("min_score", min_score)

    validated = tuple(signal.validate() for signal in signals)
    if len({signal.signal_id for signal in validated}) != len(validated):
        raise ValueError("EDPF_FORECAST_DUPLICATE_SIGNAL_ID")

    best_by_key: dict[tuple[str, str, str, str, str, str], ForecastSignal] = {}
    duplicates: list[ForecastSignal] = []
    for signal in validated:
        key = signal.semantic_key()
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = signal
            continue
        if (signal.opportunity_score(), signal.signal_id) > (current.opportunity_score(), current.signal_id):
            duplicates.append(current)
            best_by_key[key] = signal
        else:
            duplicates.append(signal)

    unique = tuple(best_by_key.values())
    ranked = tuple(sorted(unique, key=lambda item: (-item.opportunity_score(), item.signal_id)))
    selected_signals = tuple(item for item in ranked if item.opportunity_score() >= threshold)[:max_questions]
    selected_ids = {item.signal_id for item in selected_signals}

    opportunities: list[ForecastOpportunity] = []
    for signal in selected_signals:
        request_id = _request_id(signal)
        question = signal.to_question(request_id=request_id)
        question.validate()
        opportunities.append(
            ForecastOpportunity(
                signal_id=signal.signal_id,
                score=signal.opportunity_score(),
                request_id=request_id,
                question=question,
                reason_codes=(
                    "DECISION_SENSITIVE_UNCERTAINTY",
                    "MEASURABLE_OUTCOME_CONTRACT",
                    "PROSPECTIVE_WINDOW_SEPARATED",
                ),
            )
        )

    held: list[HeldForecastSignal] = []
    for signal in duplicates:
        held.append(HeldForecastSignal(signal.signal_id, signal.opportunity_score(), ("SEMANTIC_DUPLICATE",)))
    for signal in ranked:
        if signal.signal_id in selected_ids:
            continue
        score = signal.opportunity_score()
        reason = "BELOW_INFORMATION_VALUE_FLOOR" if score < threshold else "QUESTION_BUDGET_EXHAUSTED"
        held.append(HeldForecastSignal(signal.signal_id, score, (reason,)))

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "candidate_count": len(validated),
        "unique_candidate_count": len(unique),
        "selected_count": len(opportunities),
        "opportunities": tuple(opportunities),
        "held": tuple(sorted(held, key=lambda item: item.signal_id)),
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
