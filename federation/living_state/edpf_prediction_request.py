from __future__ import annotations

"""Provider-neutral request/response contract for prospective EDPF forecasts.

This module does not call a model, authorize a provider request, schedule work,
or write Living State. It ranks candidate predictors with the admitted EDPF
allocation function, compiles deterministic request packets, validates explicit
forecast responses, and converts a valid response into the admitted
``EDPF_PREDICTION`` ingress envelope for a separate caller to submit.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    PredictorProfile,
    predictor_allocation_weight,
)
from .edpf_prediction_adapter import OPEN_STATE
from .ingress import EDPF_PREDICTION_EVENT, IngressEnvelope
from .types import NodeKind, ProofMaturity

SCHEMA = "SOVARA_EDPF_PREDICTION_REQUEST_CONTRACT_V1"
PROBABILITY_BASIS = "EXPLICIT_FORECAST_NOT_POLICY_SCORE_TRANSFORM"
MIN_INDEPENDENT_SOURCES = 2
MAX_PREDICTORS = 5


class RequestState(str, Enum):
    REQUEST_CONTRACT_READY = "REQUEST_CONTRACT_READY"
    HOLD_INDEPENDENT_SOURCE_DIVERSITY = "HOLD_INDEPENDENT_SOURCE_DIVERSITY"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("EDPF_REQUEST_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


def _sha40(value: str) -> str:
    candidate = str(value).lower().strip()
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise ValueError("EDPF_REQUEST_SOURCE_HEAD_INVALID")
    return candidate


def _safe_context(value: Mapping[str, Any]) -> dict[str, Any]:
    raw = json.loads(_stable_json(dict(value)))
    forbidden = ("secret", "token", "password", "api_key", "apikey", "credential", "private_key", "client_secret")

    def walk(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                lowered = str(key).lower().replace("-", "_")
                if any(marker in lowered for marker in forbidden):
                    raise ValueError(f"EDPF_REQUEST_CONTEXT_CREDENTIAL_LIKE_KEY:{key}")
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(raw)
    return raw


@dataclass(frozen=True, slots=True)
class PredictionQuestion:
    request_id: str
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
    evidence_refs: tuple[str, ...] = ()
    context: Mapping[str, Any] | None = None
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"

    def validate(self) -> "PredictionQuestion":
        for name in ("request_id", "mission_id", "mission_snapshot_digest", "domain", "event", "outcome_criterion", "matter_scope"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"EDPF_REQUEST_{name.upper()}_REQUIRED")
        _sha40(self.system_source_head_sha)
        created = _time(self.created_at)
        deadline = _time(self.prediction_deadline_at)
        not_before = _time(self.outcome_not_before_at)
        outcome_deadline = _time(self.outcome_deadline_at)
        if not created < deadline < not_before <= outcome_deadline:
            raise ValueError("EDPF_REQUEST_TEMPORAL_CONTRACT_INVALID")
        if self.sensitivity not in {"PUBLIC_SAFE", "PRIVATE_LOCAL"}:
            raise ValueError("EDPF_REQUEST_SENSITIVITY_INVALID")
        _safe_context(self.context or {})
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise ValueError("EDPF_REQUEST_DUPLICATE_EVIDENCE_REF")
        return self


@dataclass(frozen=True, slots=True)
class PredictorCandidate:
    predictor_id: str
    source_fingerprint: str
    predictor_version: str
    profile: PredictorProfile
    relevance: float
    independence: float
    expected_information_gain: float
    cost: float
    latency: float
    provider_backed: bool = False

    def validate(self, *, domain: str) -> "PredictorCandidate":
        if not self.predictor_id.strip() or not self.source_fingerprint.strip() or not self.predictor_version.strip():
            raise ValueError("EDPF_REQUEST_PREDICTOR_IDENTITY_REQUIRED")
        self.profile.validate()
        if self.profile.predictor_id != self.predictor_id or self.profile.domain != domain:
            raise ValueError("EDPF_REQUEST_PREDICTOR_PROFILE_MISMATCH")
        for name in ("relevance", "independence", "expected_information_gain", "cost", "latency"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_REQUEST_{name.upper()}_OUT_OF_RANGE")
        return self

    def allocation_weight(self) -> float:
        return predictor_allocation_weight(
            self.profile,
            relevance=self.relevance,
            independence=self.independence,
            expected_information_gain=self.expected_information_gain,
            cost=self.cost,
            latency=self.latency,
        )


@dataclass(frozen=True, slots=True)
class PredictionRequestPacket:
    schema: str
    packet_id: str
    request_id: str
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
    predictor_id: str
    predictor_source_fingerprint: str
    predictor_version: str
    provider_backed: bool
    allocation_weight: float
    evidence_refs: tuple[str, ...]
    context: Mapping[str, Any]
    matter_scope: str
    sensitivity: str
    response_requirements: tuple[str, ...]
    request_text: str
    provider_call_authorized: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class PredictionRequestSet:
    schema: str
    request_id: str
    state: RequestState
    candidate_count: int
    selected_count: int
    independent_source_count: int
    selected_predictor_ids: tuple[str, ...]
    packets: tuple[PredictionRequestPacket, ...]
    provider_call_authorized: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    blockers: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class PredictionResponseEnvelope:
    response_id: str
    request_id: str
    packet_id: str
    request_receipt_sha256: str
    predictor_id: str
    predictor_source_fingerprint: str
    predictor_version: str
    observed_at: str
    probability: float
    expected_value: float
    expected_latency: float
    expected_owner_burden: float
    evidence_refs: tuple[str, ...]
    proof_ref: str
    proof_maturity: ProofMaturity
    probability_basis: str = PROBABILITY_BASIS

    def validate(self, packet: PredictionRequestPacket) -> "PredictionResponseEnvelope":
        if not self.response_id.strip() or not self.proof_ref.strip():
            raise ValueError("EDPF_RESPONSE_IDENTITY_REQUIRED")
        if self.request_id != packet.request_id or self.packet_id != packet.packet_id:
            raise ValueError("EDPF_RESPONSE_REQUEST_BINDING_MISMATCH")
        if self.request_receipt_sha256 != packet.receipt_sha256:
            raise ValueError("EDPF_RESPONSE_REQUEST_RECEIPT_MISMATCH")
        if (self.predictor_id, self.predictor_source_fingerprint, self.predictor_version) != (
            packet.predictor_id,
            packet.predictor_source_fingerprint,
            packet.predictor_version,
        ):
            raise ValueError("EDPF_RESPONSE_PREDICTOR_BINDING_MISMATCH")
        observed = _time(self.observed_at)
        if observed < _time(packet.created_at) or observed > _time(packet.prediction_deadline_at):
            raise ValueError("EDPF_RESPONSE_OUTSIDE_PREDICTION_WINDOW")
        if self.probability_basis != PROBABILITY_BASIS:
            raise ValueError("EDPF_RESPONSE_EXPLICIT_PROBABILITY_ATTESTATION_REQUIRED")
        if not 0.0 <= float(self.probability) <= 1.0:
            raise ValueError("EDPF_RESPONSE_PROBABILITY_OUT_OF_RANGE")
        if not math.isfinite(float(self.expected_value)):
            raise ValueError("EDPF_RESPONSE_EXPECTED_VALUE_NONFINITE")
        for name in ("expected_latency", "expected_owner_burden"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"EDPF_RESPONSE_{name.upper()}_OUT_OF_RANGE")
        if self.proof_maturity in {ProofMaturity.UNKNOWN, ProofMaturity.DECLARED}:
            raise ValueError("EDPF_RESPONSE_PROOF_MATURITY_TOO_WEAK")
        if packet.provider_backed and self.proof_maturity not in {ProofMaturity.PROVIDER_READBACK, ProofMaturity.RECEIPT_VERIFIED}:
            raise ValueError("EDPF_RESPONSE_PROVIDER_NATIVE_READBACK_REQUIRED")
        if not self.evidence_refs:
            raise ValueError("EDPF_RESPONSE_EVIDENCE_REQUIRED")
        return self


def _select_candidates(
    question: PredictionQuestion,
    candidates: Sequence[PredictorCandidate],
    *,
    max_predictors: int,
    min_independent_sources: int,
) -> tuple[PredictorCandidate, ...]:
    if not candidates:
        raise ValueError("EDPF_REQUEST_PREDICTOR_CANDIDATE_REQUIRED")
    if not 1 <= max_predictors <= MAX_PREDICTORS:
        raise ValueError("EDPF_REQUEST_MAX_PREDICTORS_INVALID")
    if not 1 <= min_independent_sources <= max_predictors:
        raise ValueError("EDPF_REQUEST_MIN_INDEPENDENT_SOURCES_INVALID")
    validated = tuple(item.validate(domain=question.domain) for item in candidates)
    if len({item.predictor_id for item in validated}) != len(validated):
        raise ValueError("EDPF_REQUEST_DUPLICATE_PREDICTOR_ID")
    ranked = tuple(sorted(validated, key=lambda item: (-item.allocation_weight(), item.predictor_id)))

    selected: list[PredictorCandidate] = []
    used_sources: set[str] = set()
    for item in ranked:
        if item.source_fingerprint in used_sources:
            continue
        selected.append(item)
        used_sources.add(item.source_fingerprint)
        if len(used_sources) >= min_independent_sources:
            break
    for item in ranked:
        if len(selected) >= max_predictors:
            break
        if item not in selected:
            selected.append(item)
    return tuple(selected[:max_predictors])


def _packet(question: PredictionQuestion, candidate: PredictorCandidate) -> PredictionRequestPacket:
    context = _safe_context(question.context or {})
    seed = {
        "request_id": question.request_id,
        "predictor_id": candidate.predictor_id,
        "source_fingerprint": candidate.source_fingerprint,
        "predictor_version": candidate.predictor_version,
        "source_head": question.system_source_head_sha,
        "snapshot": question.mission_snapshot_digest,
    }
    packet_id = "EDPF-REQ-" + _digest(seed).split(":", 1)[1][:20].upper()
    requirements = (
        "Return one explicit probability in [0,1] for the defined event.",
        "Do not transform policy-market robust scores, route ranks, utility scores or consensus counts into probability.",
        f"Set probability_basis exactly to {PROBABILITY_BASIS}.",
        "Return expected_value as a finite number and expected_latency/expected_owner_burden in [0,1].",
        "Cite only evidence available before the prediction deadline.",
        "Do not claim execution, provider state or effects not supported by readback.",
    )
    request_text = (
        f"EDPF prospective forecast request {question.request_id}.\n"
        f"Mission: {question.mission_id}\nDomain: {question.domain}\nEvent: {question.event}\n"
        f"Outcome criterion: {question.outcome_criterion}\n"
        f"Prediction deadline: {question.prediction_deadline_at}\n"
        f"Outcome observation window: {question.outcome_not_before_at} through {question.outcome_deadline_at}\n"
        f"System source head: {question.system_source_head_sha}\n"
        f"Mission snapshot: {question.mission_snapshot_digest}\n"
        f"Evidence refs: {', '.join(question.evidence_refs) or 'none'}\n"
        f"Context JSON: {_stable_json(context)}\n\n"
        + "\n".join(f"- {item}" for item in requirements)
    )
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "packet_id": packet_id,
        "request_id": question.request_id,
        "mission_id": question.mission_id,
        "system_source_head_sha": _sha40(question.system_source_head_sha),
        "mission_snapshot_digest": question.mission_snapshot_digest,
        "domain": question.domain,
        "event": question.event,
        "outcome_criterion": question.outcome_criterion,
        "created_at": question.created_at,
        "prediction_deadline_at": question.prediction_deadline_at,
        "outcome_not_before_at": question.outcome_not_before_at,
        "outcome_deadline_at": question.outcome_deadline_at,
        "predictor_id": candidate.predictor_id,
        "predictor_source_fingerprint": candidate.source_fingerprint,
        "predictor_version": candidate.predictor_version,
        "provider_backed": candidate.provider_backed,
        "allocation_weight": candidate.allocation_weight(),
        "evidence_refs": tuple(question.evidence_refs),
        "context": context,
        "matter_scope": question.matter_scope,
        "sensitivity": question.sensitivity,
        "response_requirements": requirements,
        "request_text": request_text,
        "provider_call_authorized": False,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "stable_self_promotion_allowed": False,
    }
    body["receipt_sha256"] = _digest(body)
    return PredictionRequestPacket(**body)


def compile_prediction_request_set(
    question: PredictionQuestion,
    candidates: Sequence[PredictorCandidate],
    *,
    max_predictors: int = 3,
    min_independent_sources: int = MIN_INDEPENDENT_SOURCES,
) -> PredictionRequestSet:
    question.validate()
    selected = _select_candidates(
        question,
        candidates,
        max_predictors=max_predictors,
        min_independent_sources=min_independent_sources,
    )
    packets = tuple(_packet(question, item) for item in selected)
    independent_sources = len({item.source_fingerprint for item in selected})
    blockers: list[str] = []
    if independent_sources < min_independent_sources:
        blockers.append("INDEPENDENT_PREDICTOR_SOURCE_DIVERSITY_REQUIRED")
        state = RequestState.HOLD_INDEPENDENT_SOURCE_DIVERSITY
    else:
        state = RequestState.REQUEST_CONTRACT_READY
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "request_id": question.request_id,
        "state": state,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "independent_source_count": independent_sources,
        "selected_predictor_ids": tuple(item.predictor_id for item in selected),
        "packets": packets,
        "provider_call_authorized": False,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "stable_self_promotion_allowed": False,
        "blockers": tuple(blockers),
    }
    body["receipt_sha256"] = _digest(body)
    return PredictionRequestSet(**body)


def response_to_ingress_envelope(
    packet: PredictionRequestPacket,
    response: PredictionResponseEnvelope,
) -> IngressEnvelope:
    response.validate(packet)
    prediction_id = "edpf:prediction:" + _digest(
        {"request_id": packet.request_id, "packet_id": packet.packet_id, "predictor_id": packet.predictor_id}
    ).split(":", 1)[1][:32]
    event_id = "edpf:ingress:" + _digest(
        {"prediction_id": prediction_id, "response_id": response.response_id}
    ).split(":", 1)[1][:32]
    evidence_refs = tuple(dict.fromkeys((*packet.evidence_refs, *response.evidence_refs)))
    envelope = IngressEnvelope(
        event_id=event_id,
        event_class=EDPF_PREDICTION_EVENT,
        source_ref=f"predictor:{response.predictor_id}:{response.predictor_source_fingerprint}",
        observed_at=response.observed_at,
        proof_ref=response.proof_ref,
        proof_maturity=response.proof_maturity,
        object_id=prediction_id,
        object_kind=NodeKind.EXPERIMENT.value,
        state=OPEN_STATE,
        payload={
            "mission_id": packet.mission_id,
            "system_source_head_sha": packet.system_source_head_sha,
            "mission_snapshot_digest": packet.mission_snapshot_digest,
            "predictor_source_fingerprint": response.predictor_source_fingerprint,
            "predictor_version": response.predictor_version,
            "predictor_id": response.predictor_id,
            "domain": packet.domain,
            "event": packet.event,
            "probability": float(response.probability),
            "expected_value": float(response.expected_value),
            "expected_latency": float(response.expected_latency),
            "expected_owner_burden": float(response.expected_owner_burden),
            "evidence_refs": evidence_refs,
        },
        confidence=1.0,
        matter_scope=packet.matter_scope,
        sensitivity=packet.sensitivity,
    )
    envelope.validate(allow_private_local=packet.sensitivity == "PRIVATE_LOCAL")
    return envelope


__all__ = [
    "SCHEMA",
    "PROBABILITY_BASIS",
    "RequestState",
    "PredictionQuestion",
    "PredictorCandidate",
    "PredictionRequestPacket",
    "PredictionRequestSet",
    "PredictionResponseEnvelope",
    "compile_prediction_request_set",
    "response_to_ingress_envelope",
]
