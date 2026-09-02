from __future__ import annotations

"""Prospective EDPF prediction capture on the existing Living State event journal.

This adapter deliberately creates no new database, scheduler, authority plane,
provider executor, or prediction ledger. Predictions are ordinary
``NodeKind.EXPERIMENT`` observations in ``LivingWorldModel``. Later outcomes
resolve the same node with separate proof and can be compiled into the admitted
EDPF shadow-prediction court.

Authority boundary: A1_INTERNAL only; zero external effects.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.edpf_shadow_prediction_court_v1 import (
    EvidenceMode,
    ShadowPredictionPair,
)
from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    Prediction,
    PredictionOutcome,
)
from .model import LivingWorldModel
from .types import NodeKind, ProofMaturity, Provenance, WorldNode

SCHEMA = "SOVARA_EDPF_LIVING_STATE_PREDICTION_ADAPTER_V1"
OPEN_STATE = "PREDICTION_OPEN"
RESOLVED_TRUE_STATE = "PREDICTION_RESOLVED_OCCURRED"
RESOLVED_FALSE_STATE = "PREDICTION_RESOLVED_NOT_OCCURRED"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("EDPF_LIVING_STATE_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(timezone.utc)


def _sha40(value: str, code: str) -> str:
    candidate = str(value).lower().strip()
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise ValueError(code)
    return candidate


def _node_id(prediction_id: str) -> str:
    if not str(prediction_id).strip():
        raise ValueError("EDPF_LIVING_STATE_PREDICTION_ID_REQUIRED")
    return "edpf:prediction:" + sha256(str(prediction_id).encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True, slots=True)
class ProspectivePredictionRecord:
    mission_id: str
    system_source_head_sha: str
    mission_snapshot_digest: str
    predictor_source_fingerprint: str
    predictor_version: str
    observed_at: str
    prediction_proof_ref: str
    prediction: Prediction
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"
    ttl_seconds: int = 31_536_000

    def validate(self) -> "ProspectivePredictionRecord":
        if not self.mission_id.strip() or not self.mission_snapshot_digest.strip():
            raise ValueError("EDPF_LIVING_STATE_MISSION_IDENTITY_REQUIRED")
        _sha40(self.system_source_head_sha, "EDPF_LIVING_STATE_SYSTEM_SOURCE_HEAD_INVALID")
        if not self.predictor_source_fingerprint.strip() or not self.predictor_version.strip():
            raise ValueError("EDPF_LIVING_STATE_PREDICTOR_IDENTITY_REQUIRED")
        _time(self.observed_at)
        if not self.prediction_proof_ref.strip():
            raise ValueError("EDPF_LIVING_STATE_PREDICTION_PROOF_REQUIRED")
        if not self.matter_scope.strip():
            raise ValueError("EDPF_LIVING_STATE_MATTER_SCOPE_REQUIRED")
        if self.ttl_seconds <= 0:
            raise ValueError("EDPF_LIVING_STATE_TTL_INVALID")
        self.prediction.validate()
        return self


@dataclass(frozen=True, slots=True)
class ProspectiveOutcomeRecord:
    prediction_id: str
    observed_at: str
    outcome_source_ref: str
    proof_maturity: ProofMaturity
    outcome: PredictionOutcome
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"
    ttl_seconds: int = 31_536_000

    def validate(self) -> "ProspectiveOutcomeRecord":
        if not self.prediction_id.strip() or not self.outcome_source_ref.strip():
            raise ValueError("EDPF_LIVING_STATE_OUTCOME_IDENTITY_REQUIRED")
        _time(self.observed_at)
        if not self.matter_scope.strip():
            raise ValueError("EDPF_LIVING_STATE_MATTER_SCOPE_REQUIRED")
        if self.ttl_seconds <= 0:
            raise ValueError("EDPF_LIVING_STATE_TTL_INVALID")
        if self.proof_maturity in (ProofMaturity.UNKNOWN, ProofMaturity.DECLARED):
            raise ValueError("EDPF_LIVING_STATE_OUTCOME_PROOF_TOO_WEAK")
        self.outcome.validate()
        if self.outcome.prediction_id != self.prediction_id:
            raise ValueError("EDPF_LIVING_STATE_OUTCOME_PREDICTION_MISMATCH")
        if not self.outcome.proof_refs:
            raise ValueError("EDPF_LIVING_STATE_OUTCOME_PROOF_REQUIRED")
        return self


def _prediction_payload(record: ProspectivePredictionRecord) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "prospective_capture": True,
        "mission_id": record.mission_id,
        "system_source_head_sha": record.system_source_head_sha.lower(),
        "mission_snapshot_digest": record.mission_snapshot_digest,
        "predictor_source_fingerprint": record.predictor_source_fingerprint,
        "predictor_version": record.predictor_version,
        "prediction_observed_at": record.observed_at,
        "prediction_proof_ref": record.prediction_proof_ref,
        "prediction": asdict(record.prediction),
        "resolution": None,
    }


def record_prospective_prediction(
    model: LivingWorldModel,
    record: ProspectivePredictionRecord,
):
    """Append exactly one immutable prospective prediction observation."""

    record.validate()
    node_id = _node_id(record.prediction.prediction_id)
    if node_id in model.current_nodes():
        raise ValueError("EDPF_LIVING_STATE_PREDICTION_ALREADY_RECORDED")
    provenance = Provenance(
        source_ref=f"git:{record.system_source_head_sha.lower()}",
        proof_ref=record.prediction_proof_ref,
        observed_at=record.observed_at,
        proof_maturity=ProofMaturity.SOURCE_READBACK,
        ttl_seconds=record.ttl_seconds,
        confidence=1.0,
        authority_ceiling="A1_INTERNAL",
        matter_scope=record.matter_scope,
        sensitivity=record.sensitivity,
        source_class="EDPF_PROSPECTIVE_PREDICTION",
    ).validate()
    node = WorldNode(
        node_id=node_id,
        kind=NodeKind.EXPERIMENT,
        label=f"EDPF prediction {record.prediction.prediction_id}",
        state=OPEN_STATE,
        payload=_prediction_payload(record),
        provenance=provenance,
        external_effect=False,
    ).validate()
    return model.observe_node(node)


def resolve_prospective_prediction(
    model: LivingWorldModel,
    resolution: ProspectiveOutcomeRecord,
):
    """Resolve one previously captured prediction with later, separate proof."""

    resolution.validate()
    node_id = _node_id(resolution.prediction_id)
    current = model.current_nodes().get(node_id)
    if current is None:
        raise ValueError("EDPF_LIVING_STATE_OPEN_PREDICTION_REQUIRED")
    if current.kind != NodeKind.EXPERIMENT or current.state != OPEN_STATE:
        raise ValueError("EDPF_LIVING_STATE_PREDICTION_NOT_OPEN")
    if current.provenance.matter_scope != resolution.matter_scope:
        raise ValueError("EDPF_LIVING_STATE_MATTER_SCOPE_MISMATCH")
    payload = dict(current.payload)
    if payload.get("schema") != SCHEMA or not payload.get("prospective_capture"):
        raise ValueError("EDPF_LIVING_STATE_FOREIGN_EXPERIMENT_NODE")
    raw_prediction = dict(payload.get("prediction", {}))
    prediction = Prediction(**raw_prediction).validate()
    if prediction.prediction_id != resolution.prediction_id:
        raise ValueError("EDPF_LIVING_STATE_PREDICTION_NODE_MISMATCH")
    if _time(resolution.observed_at) <= _time(str(payload["prediction_observed_at"])):
        raise ValueError("EDPF_LIVING_STATE_TEMPORAL_LEAKAGE")
    pre_refs = set(prediction.evidence_refs) | {str(payload["prediction_proof_ref"])}
    outcome_refs = set(resolution.outcome.proof_refs)
    if pre_refs & outcome_refs:
        raise ValueError("EDPF_LIVING_STATE_OUTCOME_PROOF_LEAKED_INTO_PREDICTION")

    observed = 1.0 if resolution.outcome.occurred else 0.0
    probability_error = float(prediction.probability) - observed
    resolved_payload = dict(payload)
    resolved_payload["resolution"] = {
        "outcome_observed_at": resolution.observed_at,
        "outcome_source_ref": resolution.outcome_source_ref,
        "proof_maturity": resolution.proof_maturity.value,
        "outcome": asdict(resolution.outcome),
        "brier_score": round(probability_error * probability_error, 9),
        "absolute_probability_error": round(abs(probability_error), 9),
        "absolute_value_error": round(abs(float(prediction.expected_value) - float(resolution.outcome.realised_value)), 9),
        "absolute_latency_error": round(abs(float(prediction.expected_latency) - float(resolution.outcome.realised_latency)), 9),
        "absolute_owner_burden_error": round(abs(float(prediction.expected_owner_burden) - float(resolution.outcome.realised_owner_burden)), 9),
    }
    proof_ref = "edpf-outcome:" + _digest(sorted(outcome_refs))
    provenance = Provenance(
        source_ref=resolution.outcome_source_ref,
        proof_ref=proof_ref,
        observed_at=resolution.observed_at,
        proof_maturity=resolution.proof_maturity,
        ttl_seconds=resolution.ttl_seconds,
        confidence=1.0,
        authority_ceiling="A1_INTERNAL",
        matter_scope=resolution.matter_scope,
        sensitivity=resolution.sensitivity,
        source_class="EDPF_PROSPECTIVE_OUTCOME",
    ).validate()
    state = RESOLVED_TRUE_STATE if resolution.outcome.occurred else RESOLVED_FALSE_STATE
    resolved = WorldNode(
        node_id=node_id,
        kind=NodeKind.EXPERIMENT,
        label=current.label,
        state=state,
        payload=resolved_payload,
        provenance=provenance,
        external_effect=False,
    ).validate()
    return model.observe_node(resolved)


def compile_real_shadow_pairs(
    events: Sequence[Mapping[str, Any]],
) -> tuple[ShadowPredictionPair, ...]:
    """Compile prospective open->resolved event pairs from an exported journal.

    The compiler accepts only an OPEN observation that occurs earlier in the same
    event chain than its RESOLVED observation. The prediction-time evidence and
    later outcome proof remain disjoint by construction.
    """

    open_nodes: dict[str, tuple[int, Mapping[str, Any]]] = {}
    pairs: list[ShadowPredictionPair] = []
    for raw_event in events:
        if str(raw_event.get("event_type")) not in {"NODE_OBSERVED", "NODE_TRANSITIONED"}:
            continue
        sequence = int(raw_event.get("sequence", 0))
        node = dict(dict(raw_event.get("payload", {})).get("node", {}))
        if str(node.get("kind")) not in (NodeKind.EXPERIMENT.value, str(NodeKind.EXPERIMENT)):
            continue
        payload = dict(node.get("payload", {}))
        if payload.get("schema") != SCHEMA or not payload.get("prospective_capture"):
            continue
        node_id = str(node.get("node_id", ""))
        state = str(node.get("state", ""))
        if state == OPEN_STATE:
            if node_id in open_nodes:
                raise ValueError("EDPF_LIVING_STATE_DUPLICATE_OPEN_EVENT")
            open_nodes[node_id] = (sequence, node)
            continue
        if state not in (RESOLVED_TRUE_STATE, RESOLVED_FALSE_STATE):
            continue
        if node_id not in open_nodes:
            raise ValueError("EDPF_LIVING_STATE_RESOLUTION_WITHOUT_PRIOR_OPEN")
        open_sequence, open_node = open_nodes[node_id]
        if open_sequence >= sequence:
            raise ValueError("EDPF_LIVING_STATE_EVENT_ORDER_INVALID")
        open_payload = dict(open_node["payload"])
        resolved_payload = payload
        if resolved_payload.get("prediction") != open_payload.get("prediction"):
            raise ValueError("EDPF_LIVING_STATE_PREDICTION_MUTATED_AFTER_CUTOFF")
        raw_prediction = dict(open_payload["prediction"])
        raw_outcome = dict(dict(resolved_payload["resolution"])["outcome"])
        prediction = Prediction(**raw_prediction).validate()
        raw_outcome["proof_refs"] = tuple(raw_outcome.get("proof_refs", ()))
        outcome = PredictionOutcome(**raw_outcome).validate()
        cutoff = int(_time(str(open_payload["prediction_observed_at"])).timestamp())
        observed = int(_time(str(dict(resolved_payload["resolution"])["outcome_observed_at"])).timestamp())
        pre_refs = tuple(dict.fromkeys((*prediction.evidence_refs, str(open_payload["prediction_proof_ref"]))))
        pairs.append(
            ShadowPredictionPair(
                pair_id="prospective:" + _digest({"node_id": node_id, "open_sequence": open_sequence, "resolved_sequence": sequence})[:24],
                mission_id=str(open_payload["mission_id"]),
                source_head_sha=_sha40(str(open_payload["system_source_head_sha"]), "EDPF_LIVING_STATE_SYSTEM_SOURCE_HEAD_INVALID"),
                predictor_source_fingerprint=str(open_payload["predictor_source_fingerprint"]),
                prediction_cutoff_epoch=cutoff,
                outcome_observed_epoch=observed,
                prediction=prediction,
                outcome=outcome,
                pre_outcome_evidence_refs=pre_refs,
                outcome_proof_refs=tuple(outcome.proof_refs),
                evidence_mode=EvidenceMode.REAL_MISSION,
            ).validate()
        )
        del open_nodes[node_id]
    return tuple(sorted(pairs, key=lambda item: (item.prediction_cutoff_epoch, item.pair_id)))
