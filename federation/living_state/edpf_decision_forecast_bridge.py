from __future__ import annotations

"""Bridge canonical EDPF SEEK_EVIDENCE decisions into prospective forecasts.

The bridge is host-invoked and A1_INTERNAL. It does not invent evidence value,
forecast probabilities, outcome criteria, provider authority, or execution.
It selects only the canonical ``next_evidence_candidate_id`` already chosen by
EDPF, requires an evidence-backed measurable outcome contract, and composes the
admitted Forecast Opportunity Compiler.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    DecisionState,
    EpistemicDecisionReceipt,
    EvidenceCandidate,
    MIN_DECISION_SENSITIVITY,
)
from .edpf_forecast_opportunity import (
    ForecastOpportunitySet,
    ForecastSignal,
    compile_forecast_opportunities,
)

SCHEMA = "SOVARA_EDPF_DECISION_FORECAST_BRIDGE_V1"


class BridgeState(str, Enum):
    FORECAST_QUESTION_READY = "FORECAST_QUESTION_READY"
    HOLD = "HOLD"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _sha40(value: str) -> str:
    candidate = str(value).strip().lower()
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise ValueError("EDPF_DECISION_FORECAST_SOURCE_HEAD_INVALID")
    return candidate


def _unit(name: str, value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"EDPF_DECISION_FORECAST_{name.upper()}_OUT_OF_RANGE")
    return value


@dataclass(frozen=True, slots=True)
class DecisionForecastContext:
    mission_id: str
    system_source_head_sha: str
    mission_snapshot_digest: str
    domain: str
    created_at: str
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"
    context: Mapping[str, Any] | None = None

    def validate(self) -> "DecisionForecastContext":
        for name in ("mission_id", "mission_snapshot_digest", "domain", "created_at", "matter_scope"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"EDPF_DECISION_FORECAST_{name.upper()}_REQUIRED")
        _sha40(self.system_source_head_sha)
        if self.sensitivity not in {"PUBLIC_SAFE", "PRIVATE_LOCAL"}:
            raise ValueError("EDPF_DECISION_FORECAST_SENSITIVITY_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ForecastOutcomeContract:
    evidence_candidate_id: str
    event: str
    outcome_criterion: str
    prediction_deadline_at: str
    outcome_not_before_at: str
    outcome_deadline_at: str
    outcome_observability: float
    evidence_refs: tuple[str, ...]
    observability_basis_refs: tuple[str, ...]
    context: Mapping[str, Any] | None = None

    def validate(self) -> "ForecastOutcomeContract":
        for name in (
            "evidence_candidate_id",
            "event",
            "outcome_criterion",
            "prediction_deadline_at",
            "outcome_not_before_at",
            "outcome_deadline_at",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"EDPF_DECISION_FORECAST_{name.upper()}_REQUIRED")
        _unit("outcome_observability", self.outcome_observability)
        if not self.evidence_refs:
            raise ValueError("EDPF_DECISION_FORECAST_PRE_OUTCOME_EVIDENCE_REQUIRED")
        if not self.observability_basis_refs:
            raise ValueError("EDPF_DECISION_FORECAST_OBSERVABILITY_BASIS_REQUIRED")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("EDPF_DECISION_FORECAST_DUPLICATE_EVIDENCE_REF")
        if len(set(self.observability_basis_refs)) != len(self.observability_basis_refs):
            raise ValueError("EDPF_DECISION_FORECAST_DUPLICATE_OBSERVABILITY_BASIS_REF")
        return self


@dataclass(frozen=True, slots=True)
class DecisionForecastBridgeResult:
    schema: str
    state: BridgeState
    cycle_id: str
    source_head_sha: str
    selected_evidence_candidate_id: str | None
    signal_id: str | None
    opportunity_set: ForecastOpportunitySet | None
    reason_codes: tuple[str, ...]
    forecast_probability_generated: bool
    provider_call_authorized: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    live_predictor_weight_change_authorized: bool
    stable_self_promotion_allowed: bool
    receipt_sha256: str


def _hold(
    *,
    receipt: EpistemicDecisionReceipt,
    context: DecisionForecastContext,
    reason_codes: Sequence[str],
    selected_evidence_candidate_id: str | None = None,
    opportunity_set: ForecastOpportunitySet | None = None,
) -> DecisionForecastBridgeResult:
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "state": BridgeState.HOLD,
        "cycle_id": receipt.cycle_id,
        "source_head_sha": _sha40(context.system_source_head_sha),
        "selected_evidence_candidate_id": selected_evidence_candidate_id,
        "signal_id": None,
        "opportunity_set": opportunity_set,
        "reason_codes": tuple(reason_codes),
        "forecast_probability_generated": False,
        "provider_call_authorized": False,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "live_predictor_weight_change_authorized": False,
        "stable_self_promotion_allowed": False,
    }
    body["receipt_sha256"] = _digest(body)
    return DecisionForecastBridgeResult(**body)


def compile_decision_forecast(
    *,
    receipt: EpistemicDecisionReceipt,
    evidence_candidates: Sequence[EvidenceCandidate],
    outcome_contracts: Sequence[ForecastOutcomeContract],
    context: DecisionForecastContext,
) -> DecisionForecastBridgeResult:
    """Compile the canonical next evidence request into one forecast question.

    The bridge never chooses a different evidence candidate than EDPF did. If a
    safe measurable contract is absent, the result is HOLD rather than an
    inferred or fabricated question.
    """
    context.validate()
    if not receipt.cycle_id.strip() or not receipt.source_version.strip():
        raise ValueError("EDPF_DECISION_FORECAST_RECEIPT_IDENTITY_REQUIRED")

    if receipt.source_version != context.system_source_head_sha:
        return _hold(receipt=receipt, context=context, reason_codes=("SOURCE_EPOCH_MISMATCH",))
    if receipt.state is not DecisionState.SEEK_EVIDENCE or not receipt.next_evidence_candidate_id:
        return _hold(receipt=receipt, context=context, reason_codes=("DECISION_NOT_SEEKING_EVIDENCE",))

    candidate_ids = [item.candidate_id for item in evidence_candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("EDPF_DECISION_FORECAST_DUPLICATE_EVIDENCE_CANDIDATE_ID")
    contract_ids = [item.evidence_candidate_id for item in outcome_contracts]
    if len(set(contract_ids)) != len(contract_ids):
        raise ValueError("EDPF_DECISION_FORECAST_DUPLICATE_OUTCOME_CONTRACT_ID")

    selected_id = receipt.next_evidence_candidate_id
    candidate = next((item for item in evidence_candidates if item.candidate_id == selected_id), None)
    if candidate is None:
        return _hold(
            receipt=receipt,
            context=context,
            selected_evidence_candidate_id=selected_id,
            reason_codes=("CANONICAL_EVIDENCE_CANDIDATE_NOT_SUPPLIED",),
        )
    candidate.validate()
    if not set(candidate.resolves_claim_ids).issubset(set(receipt.claim_ids)):
        return _hold(
            receipt=receipt,
            context=context,
            selected_evidence_candidate_id=selected_id,
            reason_codes=("EVIDENCE_CANDIDATE_DECISION_CLAIM_BINDING_MISMATCH",),
        )

    contract = next((item for item in outcome_contracts if item.evidence_candidate_id == selected_id), None)
    if contract is None:
        return _hold(
            receipt=receipt,
            context=context,
            selected_evidence_candidate_id=selected_id,
            reason_codes=("MEASURABLE_OUTCOME_CONTRACT_REQUIRED",),
        )
    contract.validate()

    evidence_refs = tuple(dict.fromkeys((*contract.evidence_refs, *contract.observability_basis_refs)))
    signal_seed = {
        "cycle_id": receipt.cycle_id,
        "decision_receipt": receipt.receipt_sha256,
        "candidate_id": candidate.candidate_id,
        "mission_id": context.mission_id,
        "source_head": context.system_source_head_sha,
        "snapshot": context.mission_snapshot_digest,
        "event": contract.event,
        "criterion": contract.outcome_criterion,
    }
    signal_id = "EDPF-DECISION-FORECAST-" + _digest(signal_seed).split(":", 1)[1][:20].upper()
    merged_context = dict(context.context or {})
    merged_context.update(dict(contract.context or {}))
    merged_context.update(
        {
            "edpf_decision_cycle_id": receipt.cycle_id,
            "edpf_decision_receipt_sha256": receipt.receipt_sha256,
            "edpf_next_evidence_candidate_id": selected_id,
            "edpf_observability_basis_refs": tuple(contract.observability_basis_refs),
            "bridge_generated_event_probability": False,
        }
    )
    signal = ForecastSignal(
        signal_id=signal_id,
        mission_id=context.mission_id,
        system_source_head_sha=_sha40(context.system_source_head_sha),
        mission_snapshot_digest=context.mission_snapshot_digest,
        domain=context.domain,
        event=contract.event,
        outcome_criterion=contract.outcome_criterion,
        created_at=context.created_at,
        prediction_deadline_at=contract.prediction_deadline_at,
        outcome_not_before_at=contract.outcome_not_before_at,
        outcome_deadline_at=contract.outcome_deadline_at,
        evidence_candidate=candidate,
        outcome_observability=contract.outcome_observability,
        evidence_refs=evidence_refs,
        context=merged_context,
        matter_scope=context.matter_scope,
        sensitivity=context.sensitivity,
    )
    opportunity_set = compile_forecast_opportunities(
        (signal,),
        max_questions=1,
        min_information_value=MIN_DECISION_SENSITIVITY,
    )
    if opportunity_set.selected_count != 1:
        reasons = tuple(
            reason
            for held in opportunity_set.held
            for reason in held.reason_codes
        ) or ("FORECAST_OPPORTUNITY_NOT_ADMITTED",)
        return _hold(
            receipt=receipt,
            context=context,
            selected_evidence_candidate_id=selected_id,
            opportunity_set=opportunity_set,
            reason_codes=reasons,
        )

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "state": BridgeState.FORECAST_QUESTION_READY,
        "cycle_id": receipt.cycle_id,
        "source_head_sha": _sha40(context.system_source_head_sha),
        "selected_evidence_candidate_id": selected_id,
        "signal_id": signal_id,
        "opportunity_set": opportunity_set,
        "reason_codes": (
            "CANONICAL_SEEK_EVIDENCE_BOUND",
            "MEASURABLE_OUTCOME_CONTRACT_BOUND",
            "PROSPECTIVE_FORECAST_QUESTION_READY",
        ),
        "forecast_probability_generated": False,
        "provider_call_authorized": False,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "live_predictor_weight_change_authorized": False,
        "stable_self_promotion_allowed": False,
    }
    body["receipt_sha256"] = _digest(body)
    return DecisionForecastBridgeResult(**body)


def receipt_dict(result: DecisionForecastBridgeResult) -> dict[str, Any]:
    return asdict(result)
