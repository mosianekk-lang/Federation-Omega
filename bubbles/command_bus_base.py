from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from typing import Mapping

from benchmarking.cfbe_omega.epistemic_decision_prediction_fabric_v1 import (
    ClaimKind,
    DecisionOption,
    EvidenceCandidate,
    EvidenceClass,
    EvidenceRef,
    EpistemicClaim,
    PredictorProfile,
    decide,
)
from bubbles.apps_script_deployment_probe import run_probe as run_apps_script_deployment_probe
from bubbles.control_plane import (
    ActionRequest,
    BubblesControlPlane,
    EffectClass,
    RouteKind,
)
from bubbles.forest_background import run_background_event
from evidenceops.build_system.aaa_chat_resilience import evaluate_failure_with_aaa
from federation.living_state.edpf_decision_forecast_bridge import (
    BridgeState,
    DecisionForecastContext,
    ForecastOutcomeContract,
    compile_decision_forecast,
)
from federation.living_state.edpf_prediction_adapter import (
    RESOLVED_FALSE_STATE as EDPF_RESOLVED_FALSE_STATE,
    RESOLVED_TRUE_STATE as EDPF_RESOLVED_TRUE_STATE,
)
from federation.living_state.edpf_prediction_request import (
    PredictionResponseEnvelope,
    PredictorCandidate,
    compile_prediction_request_set,
    response_to_ingress_envelope,
)
from federation.living_state.ingress import (
    EDPF_OUTCOME_EVENT,
    IngressEnvelope,
    LivingStateIngress,
)
from federation.living_state.store import LivingStateStore
from federation.living_state.types import NodeKind, ProofMaturity


COMMAND_SCHEMA = "BUBBLES-CONTROL-COMMAND-V1"
RECEIPT_SCHEMA = "BUBBLES-COMMAND-RECEIPT-V1"
ALLOWED_ACTORS = frozenset({"mosianekk-lang"})


class CommandBusError(ValueError):
    pass


def _load_command(raw: str) -> Mapping[str, object]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CommandBusError(f"Command is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise CommandBusError("Command must be a JSON object")
    if data.get("schema") != COMMAND_SCHEMA:
        raise CommandBusError(f"Unsupported command schema: {data.get('schema')!r}")
    required = {"adapter_id", "action", "effect", "target_alias"}
    missing = sorted(required.difference(data))
    if missing:
        raise CommandBusError(f"Missing command fields: {', '.join(missing)}")
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise CommandBusError("payload must be a JSON object")
    return data


def _request_from_command(command: Mapping[str, object]) -> ActionRequest:
    try:
        effect = EffectClass(str(command["effect"]))
    except ValueError as exc:
        raise CommandBusError(f"Unsupported effect: {command.get('effect')!r}") from exc
    return ActionRequest(
        adapter_id=str(command["adapter_id"]),
        action=str(command["action"]),
        effect=effect,
        target_alias=str(command["target_alias"]),
        payload=dict(command.get("payload", {})),
    )


def _chat_failure_recovery(request: ActionRequest) -> dict[str, object]:
    event = request.payload.get("event")
    if not isinstance(event, dict):
        raise CommandBusError("recover_chat_failure requires payload.event as a JSON object")
    mission = request.payload.get("mission_packet")
    if mission is not None and not isinstance(mission, dict):
        raise CommandBusError("payload.mission_packet must be a JSON object when supplied")
    previous = request.payload.get("previous_checkpoint")
    if previous is not None and not isinstance(previous, dict):
        raise CommandBusError("payload.previous_checkpoint must be a JSON object when supplied")

    aaa = evaluate_failure_with_aaa(
        event,
        previous_checkpoint=previous,
        mission_packet=mission,
    )

    return {
        "kind": "LOCAL_CHAT_FAILURE_RECOVERY",
        "recovery": aaa["effective_recovery"],
        "aaa": {
            "schema": aaa["schema"],
            "route_retry": aaa["aaa_route_retry"],
            "learning_genes": aaa["aaa_learning_genes"],
            "receipt_sha256": aaa["aaa_receipt_sha256"],
            "base_recovery_sha256": aaa["base_recovery"]["receipt_sha256"],
        },
        "provider_effects": False,
    }


def _forest_background_event(request: ActionRequest) -> dict[str, object]:
    event = request.payload.get("event")
    if not isinstance(event, dict):
        raise CommandBusError("forest_first_omega_event requires payload.event as a sanitized JSON object")
    return {
        "kind": "LOCAL_FOREST_FIRST_OMEGA_BACKGROUND_EVENT",
        "background_receipt": run_background_event(event),
        "provider_effects": False,
    }


def _archon_apps_script_public_probe() -> dict[str, object]:
    """Run the admitted no-secret ARCHON web-app deployment probe."""
    return {
        "kind": "READ_ONLY_PUBLIC_APPS_SCRIPT_DEPLOYMENT_PROBE",
        "probe": run_apps_script_deployment_probe(),
        "provider_effects": False,
    }


def _edpf_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CommandBusError(f"{field} must be a JSON object")
    return value


def _mapping_list(value: object, field: str) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise CommandBusError(f"{field} must be a non-empty JSON array")
    items: list[Mapping[str, object]] = []
    for item in value:
        items.append(_mapping(item, field))
    return tuple(items)


def _evidence_ref(value: Mapping[str, object]) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=str(value["evidence_id"]),
        evidence_class=EvidenceClass(str(value["evidence_class"])),
        source_fingerprint=str(value["source_fingerprint"]),
        freshness=float(value["freshness"]),
        reliability=float(value["reliability"]),
        supports=float(value["supports"]),
    ).validate()


def _claim(value: Mapping[str, object]) -> EpistemicClaim:
    evidence_raw = value.get("evidence_refs")
    if not isinstance(evidence_raw, list) or not evidence_raw:
        raise CommandBusError("claims[].evidence_refs must be a non-empty JSON array")
    return EpistemicClaim(
        claim_id=str(value["claim_id"]),
        kind=ClaimKind(str(value["kind"])),
        statement=str(value["statement"]),
        probability=float(value["probability"]),
        evidence_refs=tuple(_evidence_ref(_mapping(item, "claims[].evidence_refs[]")) for item in evidence_raw),
        causal_parents=tuple(str(item) for item in value.get("causal_parents", ())),
        causal_children=tuple(str(item) for item in value.get("causal_children", ())),
        contradiction_refs=tuple(str(item) for item in value.get("contradiction_refs", ())),
        expires_at_epoch=int(value["expires_at_epoch"]) if value.get("expires_at_epoch") is not None else None,
    ).validate()


def _option(value: Mapping[str, object]) -> DecisionOption:
    return DecisionOption(
        option_id=str(value["option_id"]),
        expected_value=float(value["expected_value"]),
        success_probability=float(value["success_probability"]),
        reversibility=float(value["reversibility"]),
        information_gain=float(value["information_gain"]),
        cost=float(value["cost"]),
        latency=float(value["latency"]),
        owner_burden=float(value["owner_burden"]),
        risk=float(value["risk"]),
        external_effect=bool(value.get("external_effect", False)),
    ).validate()


def _evidence_candidate(value: Mapping[str, object]) -> EvidenceCandidate:
    resolves = value.get("resolves_claim_ids")
    if not isinstance(resolves, list) or not resolves:
        raise CommandBusError("evidence_candidates[].resolves_claim_ids must be a non-empty JSON array")
    return EvidenceCandidate(
        candidate_id=str(value["candidate_id"]),
        resolves_claim_ids=tuple(str(item) for item in resolves),
        decision_flip_probability=float(value["decision_flip_probability"]),
        uncertainty_reduction=float(value["uncertainty_reduction"]),
        acquisition_cost=float(value["acquisition_cost"]),
        acquisition_risk=float(value["acquisition_risk"]),
        freshness_gain=float(value["freshness_gain"]),
    ).validate()


def _predictor_candidate(value: Mapping[str, object], *, domain: str) -> PredictorCandidate:
    if bool(value.get("provider_backed", False)):
        raise CommandBusError("edpf_shadow_predict accepts non-provider-backed predictors only")
    predictor_id = str(value["predictor_id"])
    profile_raw = _mapping(value.get("profile", {}), "predictor.profile")
    profile = PredictorProfile(
        predictor_id=predictor_id,
        domain=domain,
        attempts=int(profile_raw.get("attempts", 0)),
        brier_sum=float(profile_raw.get("brier_sum", 0.0)),
        absolute_error_sum=float(profile_raw.get("absolute_error_sum", 0.0)),
        resolved_correct=int(profile_raw.get("resolved_correct", 0)),
    ).validate()
    return PredictorCandidate(
        predictor_id=predictor_id,
        source_fingerprint=str(value["source_fingerprint"]),
        predictor_version=str(value["predictor_version"]),
        profile=profile,
        relevance=float(value.get("relevance", 0.5)),
        independence=float(value.get("independence", 1.0)),
        expected_information_gain=float(value.get("expected_information_gain", 0.5)),
        cost=float(value.get("cost", 0.0)),
        latency=float(value.get("latency", 0.1)),
        provider_backed=False,
    ).validate(domain=domain)


def _ingress_from_mapping(value: Mapping[str, object]) -> IngressEnvelope:
    return IngressEnvelope(
        event_id=str(value["event_id"]),
        event_class=str(value["event_class"]),
        source_ref=str(value["source_ref"]),
        observed_at=str(value["observed_at"]),
        proof_ref=str(value["proof_ref"]),
        proof_maturity=ProofMaturity(str(value["proof_maturity"])),
        object_id=str(value["object_id"]),
        object_kind=str(value["object_kind"]),
        state=str(value["state"]),
        payload=_mapping(value["payload"], "prediction_bundle.prediction_envelope.payload"),
        ttl_seconds=int(value.get("ttl_seconds", 3600)),
        confidence=float(value.get("confidence", 0.7)),
        matter_scope=str(value.get("matter_scope", "GLOBAL")),
        sensitivity=str(value.get("sensitivity", "PUBLIC_SAFE")),
        authority_ceiling=str(value.get("authority_ceiling", "A1_INTERNAL")),
    )


def _edpf_shadow_predict(request: ActionRequest, *, source_ref: str) -> dict[str, object]:
    payload = request.payload
    if str(payload.get("sensitivity", "PUBLIC_SAFE")) != "PUBLIC_SAFE":
        raise CommandBusError("edpf_shadow_predict is PUBLIC_SAFE only")

    claims = tuple(_claim(item) for item in _mapping_list(payload.get("claims"), "claims"))
    options = tuple(_option(item) for item in _mapping_list(payload.get("options"), "options"))
    evidence_candidates = tuple(
        _evidence_candidate(item) for item in _mapping_list(payload.get("evidence_candidates"), "evidence_candidates")
    )
    source_head = str(payload["system_source_head_sha"]).strip().lower()
    cycle_id = str(payload["cycle_id"])
    decision = decide(
        cycle_id=cycle_id,
        source_version=source_head,
        claims=claims,
        options=options,
        evidence_candidates=evidence_candidates,
        proposer_source_fingerprints=tuple(str(item) for item in payload.get("proposer_source_fingerprints", ())),
    )

    host_time = _edpf_now()
    prediction_window_seconds = int(payload.get("prediction_window_seconds", 5))
    outcome_window_seconds = int(payload.get("outcome_window_seconds", 900))
    if not 3 <= prediction_window_seconds <= 120:
        raise CommandBusError("prediction_window_seconds must be in [3,120]")
    if not 60 <= outcome_window_seconds <= 3600:
        raise CommandBusError("outcome_window_seconds must be in [60,3600]")
    prediction_deadline = host_time + timedelta(seconds=prediction_window_seconds)
    outcome_not_before = prediction_deadline + timedelta(seconds=1)
    outcome_deadline = outcome_not_before + timedelta(seconds=outcome_window_seconds)

    context_raw = _mapping(payload.get("context", {}), "context")
    context = DecisionForecastContext(
        mission_id=str(payload["mission_id"]),
        system_source_head_sha=source_head,
        mission_snapshot_digest=str(payload["mission_snapshot_digest"]),
        domain=str(payload["domain"]),
        created_at=host_time.isoformat(),
        matter_scope=str(payload.get("matter_scope", "GLOBAL")),
        sensitivity="PUBLIC_SAFE",
        context=context_raw,
    )
    outcome_contract = ForecastOutcomeContract(
        evidence_candidate_id=str(decision.next_evidence_candidate_id or ""),
        event=str(payload["event"]),
        outcome_criterion=str(payload["outcome_criterion"]),
        prediction_deadline_at=prediction_deadline.isoformat(),
        outcome_not_before_at=outcome_not_before.isoformat(),
        outcome_deadline_at=outcome_deadline.isoformat(),
        outcome_observability=float(payload["outcome_observability"]),
        evidence_refs=tuple(str(item) for item in payload.get("evidence_refs", ())),
        observability_basis_refs=tuple(str(item) for item in payload.get("observability_basis_refs", ())),
        context=_mapping(payload.get("outcome_context", {}), "outcome_context"),
    )
    bridge = compile_decision_forecast(
        receipt=decision,
        evidence_candidates=evidence_candidates,
        outcome_contracts=(outcome_contract,),
        context=context,
    )
    if bridge.state is not BridgeState.FORECAST_QUESTION_READY:
        return {
            "kind": "EDPF_SHADOW_PREDICTION_HOST",
            "state": "HOLD",
            "decision": asdict(decision),
            "bridge": asdict(bridge),
            "forecast_probability_generated_by_host": False,
            "provider_effects": False,
            "external_effects": 0,
        }

    assert bridge.opportunity_set is not None
    question = bridge.opportunity_set.opportunities[0].question
    predictor = _predictor_candidate(_mapping(payload["predictor"], "predictor"), domain=question.domain)
    request_set = compile_prediction_request_set(
        question,
        (predictor,),
        max_predictors=1,
        min_independent_sources=1,
    )
    packet = request_set.packets[0]
    forecast = _mapping(payload["forecast"], "forecast")
    forecast_evidence_refs = tuple(str(item) for item in forecast.get("evidence_refs", ()))
    response = PredictionResponseEnvelope(
        response_id=str(forecast["response_id"]),
        request_id=packet.request_id,
        packet_id=packet.packet_id,
        request_receipt_sha256=packet.receipt_sha256,
        predictor_id=packet.predictor_id,
        predictor_source_fingerprint=packet.predictor_source_fingerprint,
        predictor_version=packet.predictor_version,
        observed_at=host_time.isoformat(),
        probability=float(forecast["probability"]),
        expected_value=float(forecast["expected_value"]),
        expected_latency=float(forecast["expected_latency"]),
        expected_owner_burden=float(forecast["expected_owner_burden"]),
        evidence_refs=forecast_evidence_refs,
        proof_ref=f"runtime:{source_ref}#edpf-shadow-forecast",
        proof_maturity=ProofMaturity.RUNTIME_READBACK,
    ).validate(packet)
    prediction_envelope = response_to_ingress_envelope(packet, response)

    with tempfile.TemporaryDirectory() as td:
        with LivingStateStore(Path(td) / "living.sqlite3") as store:
            ingress_receipt = LivingStateIngress(store).ingest(prediction_envelope)
            snapshot = store.restore().snapshot(now=response.observed_at)

    return {
        "kind": "EDPF_SHADOW_PREDICTION_HOST",
        "state": "PREDICTION_RECORDED",
        "decision": asdict(decision),
        "bridge": asdict(bridge),
        "request_set": asdict(request_set),
        "selected_packet": asdict(packet),
        "response": asdict(response),
        "prediction_ingress_receipt": asdict(ingress_receipt),
        "living_state_snapshot": snapshot,
        "portable_resolution_bundle": {
            "prediction_envelope": asdict(prediction_envelope),
            "prediction_id": prediction_envelope.object_id,
            "outcome_not_before_at": outcome_not_before.isoformat(),
            "outcome_deadline_at": outcome_deadline.isoformat(),
            "forecast_probability": response.probability,
            "forecast_response_id": response.response_id,
            "forecast_proof_ref": response.proof_ref,
        },
        "single_predictor_shadow_canary": True,
        "single_predictor_allocation_or_superiority_proven": False,
        "forecast_probability_generated_by_host": False,
        "forecast_probability_supplied_by_predictor": True,
        "prediction_accuracy_proven_at_ingress": False,
        "provider_effects": False,
        "external_effects": 0,
    }


def _edpf_shadow_resolve(request: ActionRequest) -> dict[str, object]:
    payload = request.payload
    bundle = _mapping(payload.get("prediction_bundle"), "prediction_bundle")
    prediction_envelope = _ingress_from_mapping(
        _mapping(bundle.get("prediction_envelope"), "prediction_bundle.prediction_envelope")
    )
    if prediction_envelope.event_class != "EDPF_PREDICTION":
        raise CommandBusError("prediction_bundle must contain an EDPF_PREDICTION envelope")
    if prediction_envelope.sensitivity != "PUBLIC_SAFE":
        raise CommandBusError("edpf_shadow_resolve is PUBLIC_SAFE only")

    now = _edpf_now()
    not_before = datetime.fromisoformat(str(bundle["outcome_not_before_at"]).replace("Z", "+00:00"))
    deadline = datetime.fromisoformat(str(bundle["outcome_deadline_at"]).replace("Z", "+00:00"))
    if now < not_before:
        raise CommandBusError("EDPF_OUTCOME_NOT_YET_OBSERVABLE")
    if now > deadline:
        raise CommandBusError("EDPF_OUTCOME_WINDOW_EXPIRED")

    observed_receipt = _mapping(payload.get("observed_bubbles_receipt"), "observed_bubbles_receipt")
    request_record = _mapping(observed_receipt.get("request", {}), "observed_bubbles_receipt.request")
    execution = _mapping(observed_receipt.get("execution", {}), "observed_bubbles_receipt.execution")
    occurred = (
        observed_receipt.get("state") == "SUCCESS"
        and request_record.get("adapter_id") == "bubbles_command_bus"
        and request_record.get("action") == "canary"
        and execution.get("kind") == "LOCAL_COMMAND_BUS_CANARY"
    )
    receipt_canonical = json.dumps(observed_receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    observed_digest = "sha256:" + sha256(receipt_canonical.encode("utf-8")).hexdigest()
    receipt_ref = str(payload["observed_receipt_ref"])
    realised_latency = float(payload["realised_latency"])
    realised_owner_burden = float(payload["realised_owner_burden"])
    if not 0.0 <= realised_latency <= 1.0 or not 0.0 <= realised_owner_burden <= 1.0:
        raise CommandBusError("realised latency/owner burden must be in [0,1]")

    outcome_envelope = IngressEnvelope(
        event_id=f"edpf-outcome:{prediction_envelope.object_id}",
        event_class=EDPF_OUTCOME_EVENT,
        source_ref=receipt_ref,
        observed_at=now.isoformat(),
        proof_ref=observed_digest,
        proof_maturity=ProofMaturity.RUNTIME_READBACK,
        object_id=prediction_envelope.object_id,
        object_kind=NodeKind.EXPERIMENT.value,
        state=EDPF_RESOLVED_TRUE_STATE if occurred else EDPF_RESOLVED_FALSE_STATE,
        payload={
            "occurred": occurred,
            "realised_value": 1.0 if occurred else 0.0,
            "realised_latency": realised_latency,
            "realised_owner_burden": realised_owner_burden,
            "proof_refs": (receipt_ref, observed_digest),
        },
        ttl_seconds=prediction_envelope.ttl_seconds,
        confidence=1.0,
        matter_scope=prediction_envelope.matter_scope,
        sensitivity="PUBLIC_SAFE",
    )

    with tempfile.TemporaryDirectory() as td:
        with LivingStateStore(Path(td) / "living.sqlite3") as store:
            ingress = LivingStateIngress(store)
            replay_receipt = ingress.ingest(prediction_envelope)
            outcome_receipt = ingress.ingest(outcome_envelope)
            snapshot = store.restore().snapshot(now=now.isoformat())

    return {
        "kind": "EDPF_SHADOW_OUTCOME_HOST",
        "state": "OUTCOME_RECORDED",
        "prediction_replay_receipt": asdict(replay_receipt),
        "outcome_ingress_receipt": asdict(outcome_receipt),
        "living_state_snapshot": snapshot,
        "prediction_id": prediction_envelope.object_id,
        "occurred": occurred,
        "forecast_probability": float(bundle["forecast_probability"]),
        "observed_receipt_sha256": observed_digest,
        "outcome_truth_from_observed_bubbles_receipt": True,
        "provider_effects": False,
        "external_effects": 0,
        "calibration_superiority_proven": False,
        "live_predictor_weight_change_authorized": False,
    }


def execute_command(command: Mapping[str, object], *, actor: str, event_name: str, source_ref: str) -> dict[str, object]:
    if actor not in ALLOWED_ACTORS:
        return {"schema": RECEIPT_SCHEMA, "state": "CONSTRAINT", "actor": actor, "event_name": event_name,
                "source_ref": source_ref, "reason": "Actor is not allowed by the Bubbles command-bus contract.",
                "truth_boundary": "No provider action executed."}

    request = _request_from_command(command)
    control = BubblesControlPlane()
    envelope = control.command_envelope(request)
    supplied_hash = command.get("command_sha256")
    if supplied_hash is not None and supplied_hash != envelope["command_sha256"]:
        return {"schema": RECEIPT_SCHEMA, "state": "CONSTRAINT", "actor": actor, "event_name": event_name,
                "source_ref": source_ref, "command_sha256": envelope["command_sha256"],
                "reason": "Supplied command hash does not match canonical command payload.",
                "truth_boundary": "No provider action executed."}

    spec = control.adapter(request.adapter_id)
    if spec.route_kind is not RouteKind.GITHUB_COMMAND_BUS:
        return {
            "schema": RECEIPT_SCHEMA, "state": "CONSTRAINT", "actor": actor, "event_name": event_name,
            "source_ref": source_ref, "command_sha256": envelope["command_sha256"],
            "request": {"adapter_id": request.adapter_id, "action": request.action, "effect": request.effect.value,
                        "target_alias": request.target_alias},
            "route_decision": {"state": "CONSTRAINT", "route_kind": spec.route_kind.value,
                               "adapter_id": request.adapter_id, "action": request.action, "missing_proofs": [],
                               "reason": "Route family rejected before proof evaluation."},
            "reason": "Command bus only executes routes classified GITHUB_COMMAND_BUS.",
            "truth_boundary": "No provider action executed.",
        }

    decision = control.decide(request)
    decision_record = {**asdict(decision), "route_kind": decision.route_kind.value if decision.route_kind else None}
    base_receipt: dict[str, object] = {
        "schema": RECEIPT_SCHEMA, "actor": actor, "event_name": event_name, "source_ref": source_ref,
        "command_sha256": envelope["command_sha256"],
        "request": {"adapter_id": request.adapter_id, "action": request.action, "effect": request.effect.value,
                    "target_alias": request.target_alias},
        "route_decision": decision_record,
    }
    if decision.state != "READY":
        return {**base_receipt, "state": "CONSTRAINT", "reason": decision.reason,
                "missing_proofs": list(decision.missing_proofs),
                "truth_boundary": "Route validation failed closed; no provider action executed."}

    if request.adapter_id == "bubbles_command_bus" and request.action == "canary":
        return {**base_receipt, "state": "SUCCESS",
                "execution": {"kind": "LOCAL_COMMAND_BUS_CANARY", "target_alias": request.target_alias,
                              "echo": request.payload.get("message", "BUBBLES_COMMAND_BUS_CANARY")},
                "truth_boundary": "SUCCESS proves ChatGPT/GitHub command ingress, route validation and runner execution only. It does not prove Google Cloud, Apps Script, AI Studio or any external provider mutation."}

    if request.adapter_id == "bubbles_command_bus" and request.action == "recover_chat_failure":
        return {**base_receipt, "state": "SUCCESS", "execution": _chat_failure_recovery(request),
                "truth_boundary": "SUCCESS proves that the Bubbles command bus invoked CFRE through Formation AAA and generated a local recovery receipt. It does not prove repair of the ChatGPT client, browser, network or OpenAI service, and it performs no external provider mutation."}

    if request.adapter_id == "bubbles_command_bus" and request.action == "forest_first_omega_event":
        return {**base_receipt, "state": "SUCCESS", "execution": _forest_background_event(request),
                "truth_boundary": "SUCCESS proves the admitted Bubbles runner processed a sanitized Forest-First Omega event and emitted a cost-governed wake decision. It does not expose private provider content, establish legal facts, or perform any external provider mutation."}

    if request.adapter_id == "bubbles_command_bus" and request.action == "probe_archon_apps_script_deployment":
        return {
            **base_receipt,
            "state": "SUCCESS",
            "execution": _archon_apps_script_public_probe(),
            "truth_boundary": (
                "SUCCESS proves the Bubbles runner executed the admitted public, read-only ARCHON Apps Script deployment probe. "
                "The nested provider classification controls any reachability or semantic claim. No credential, Apps Script mutation, "
                "Google Cloud mutation, trigger installation, or GAS-primary promotion is performed by this command."
            ),
        }

    if request.adapter_id == "bubbles_command_bus" and request.action == "edpf_shadow_predict":
        return {
            **base_receipt,
            "state": "SUCCESS",
            "execution": _edpf_shadow_predict(request, source_ref=source_ref),
            "truth_boundary": (
                "SUCCESS proves the existing Bubbles GitHub Actions host executed the canonical EDPF decision-to-forecast/request/ingress chain "
                "for a caller-supplied explicit non-provider-backed forecast. RUNTIME_READBACK proves the runner observed that stated probability; "
                "it does not prove the prediction is true, calibrated, superior, provider-native, or effect-authorized."
            ),
        }

    if request.adapter_id == "bubbles_command_bus" and request.action == "edpf_shadow_resolve":
        return {
            **base_receipt,
            "state": "SUCCESS",
            "execution": _edpf_shadow_resolve(request),
            "truth_boundary": (
                "SUCCESS proves the existing Bubbles host replayed a previously recorded EDPF prediction and resolved it from a supplied observed "
                "Bubbles canary receipt inside the declared outcome window. It does not prove predictor superiority or authorize live weight changes."
            ),
        }

    return {**base_receipt, "state": "CONSTRAINT", "reason": "Provider executor is not bound in command-bus v1.",
            "truth_boundary": "Route readiness alone is not provider authority. External execution remains blocked until a provider-specific executor supplies fresh identity, target, scope, execution and readback proof."}


def build_receipt(raw: str, *, actor: str, event_name: str, source_ref: str) -> dict[str, object]:
    try:
        command = _load_command(raw)
        return execute_command(command, actor=actor, event_name=event_name, source_ref=source_ref)
    except (CommandBusError, KeyError, ValueError) as exc:
        return {"schema": RECEIPT_SCHEMA, "state": "FAILURE", "actor": actor, "event_name": event_name,
                "source_ref": source_ref, "reason": str(exc),
                "truth_boundary": "Command validation failed; no provider action executed."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Bubbles command-bus envelope and emit a proof receipt.")
    parser.add_argument("--command-file", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = Path(args.command_file).read_text(encoding="utf-8")
    receipt = build_receipt(raw, actor=args.actor, event_name=args.event_name, source_ref=args.source_ref)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["state"] == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())