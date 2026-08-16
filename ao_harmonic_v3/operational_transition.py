from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import FederationEvent, Mission, MissionNode, NodeState, ProofNode, RiskClass, TruthState
from .provider_canary import ProviderObservation
from .runtime import AOHarmonicV3


CAPSULE_SCHEMA = "AO_HARMONIC_V3_PROVIDER_TRANSITION_CAPSULE_V1"
RECEIPT_SCHEMA = "AO_HARMONIC_V3_PROVIDER_TRANSITION_RECEIPT_V1"
_ALLOWED_PRIVACY_MODELS = {"SANITIZED_METADATA_ONLY"}
_ALLOWED_PROVIDER_RUNTIMES = {"GITHUB_ACTIONS"}


def _canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _observation(payload: dict[str, Any], phase: str) -> ProviderObservation:
    phase_payload = payload[phase]
    return ProviderObservation(
        provider=str(payload["provider"]),
        capability=str(payload["capability"]),
        object_fingerprint=str(payload["object_fingerprint"]),
        expected_status=str(phase_payload["expected_status"]),
        observed_status=str(phase_payload["observed_status"]),
        observed_at=str(phase_payload["observed_at"]),
        transport_ok=bool(phase_payload["transport_ok"]),
        semantic_match=bool(phase_payload["semantic_match"]),
        result_count=int(phase_payload.get("result_count", 0)),
        related_count=int(phase_payload.get("related_count", 0)),
        authority_ceiling=str(payload.get("authority_ceiling", "A1_READ")),
        external_effect=False,
    )


def validate_transition_capsule(payload: dict[str, Any]) -> None:
    if payload.get("schema") != CAPSULE_SCHEMA:
        raise ValueError("unsupported provider transition capsule schema")
    if not str(payload.get("capsule_id", "")).strip():
        raise ValueError("capsule_id is required")
    if payload.get("privacy_model") not in _ALLOWED_PRIVACY_MODELS:
        raise ValueError("provider transition requires sanitized metadata only")
    if payload.get("private_provider_object_identifier_persisted_publicly") is not False:
        raise ValueError("raw/private provider object identifiers may not be persisted publicly")
    if payload.get("external_effect") is not False:
        raise ValueError("operational transition capsule must remain no-effect at runtime")
    if payload.get("provider_mutation_caused_by_runtime") is not False:
        raise ValueError("this read-only operational verifier may not claim it caused provider mutation")
    before = _observation(payload, "before")
    after = _observation(payload, "after")
    before.validate()
    after.validate()
    if before.object_fingerprint != after.object_fingerprint:
        raise ValueError("before and after must refer to the same sanitized provider object")
    if before.observed_status == after.observed_status:
        raise ValueError("operational transition requires a genuine provider state change")
    transition = payload.get("expected_transition", {})
    if transition.get("from") != before.observed_status or transition.get("to") != after.observed_status:
        raise ValueError("expected transition does not match provider observations")
    prior = payload.get("prior_workflow_receipt_sha256", [])
    if not isinstance(prior, list) or len(prior) < 2:
        raise ValueError("at least two prior independent workflow receipts are required")
    for digest in prior:
        if len(str(digest)) != 64 or any(ch not in "0123456789abcdef" for ch in str(digest).lower()):
            raise ValueError("prior workflow receipts must be SHA-256 digests")


def run_operational_transition_capsule(payload: dict[str, Any], *, provider_runtime: str) -> dict[str, Any]:
    validate_transition_capsule(payload)
    if provider_runtime not in _ALLOWED_PROVIDER_RUNTIMES:
        raise ValueError("unapproved provider runtime")

    before = _observation(payload, "before")
    after = _observation(payload, "after")
    runtime = AOHarmonicV3()
    transition_digest = _canonical_sha256(payload)
    state_key = f"provider-transition:{str(payload['provider']).lower()}:{payload['object_fingerprint'][:16]}"
    mission_id = f"OPERATIONAL-{transition_digest[:16]}"

    mission = Mission(
        mission_id=mission_id,
        objective="verify AO-HARMONIC response to a real provider state transition",
        desired_outcome="preserve event history, supersede stale current state, propagate proof impact and wake dependent work",
        risk_class=RiskClass.MODERATE,
        authority_ceiling=str(payload.get("authority_ceiling", "A1_READ")),
    )
    runtime.missions.add_mission(mission)
    runtime.missions.add_node(mission_id, MissionNode("baseline_observe", "verify provider baseline"))
    runtime.missions.add_node(mission_id, MissionNode("change_observe", "verify changed provider state", dependencies=["baseline_observe"]))
    runtime.missions.add_node(mission_id, MissionNode("dependent_internal", "continue work dependent on changed provider state", dependencies=["change_observe"]))
    runtime.missions.add_node(mission_id, MissionNode("unrelated_internal", "continue independent safe internal work"))

    before_semantic = runtime.semantic_firewall.evaluate(
        transport_ok=before.transport_ok,
        semantic_match=before.semantic_match and before.expected_status == before.observed_status,
    )
    after_semantic = runtime.semantic_firewall.evaluate(
        transport_ok=after.transport_ok,
        semantic_match=after.semantic_match and after.expected_status == after.observed_status,
    )
    if before_semantic != "SUCCESS" or after_semantic != "SUCCESS":
        raise ValueError("provider transition semantic readback failed")

    before_event = FederationEvent(
        event_id=f"EVT-BEFORE-{transition_digest[:16]}",
        event_type="NEW_EVIDENCE",
        source=str(payload["provider"]),
        workstream="AO-HARMONIC-V3-OPERATIONAL-TRANSITION",
        idempotency_key=f"{transition_digest}:before",
        timestamp=before.observed_at,
        proof_class="PROVIDER_READBACK",
        authority_class=str(payload.get("authority_ceiling", "A1_READ")),
        affected_state_keys=(state_key,),
        affected_mission_nodes=("baseline_observe", "change_observe"),
        payload={"phase": "before", "status": before.observed_status, "result_count": before.result_count},
    )
    before_actions = runtime.events.emit(before_event)
    runtime.state.append_event(state_key, {"event_id": before_event.event_id, "phase": "before", "status": before.observed_status, "observed_at": before.observed_at})
    runtime.state.project(state_key, value=before.observed_status, source=f"{payload['provider']}:{payload['capability']}", verified_at=before.observed_at, status="VERIFIED")
    runtime.state.interpret(state_key, meaning="baseline provider state verified", owner_system="JARVIS_ASSURANCE_MESH", basis=[before_event.event_id], version="AO-HARMONIC-V3-OPERATIONAL-1")

    baseline_source = f"source-before-{transition_digest[:12]}"
    baseline_prop = f"proposition-before-{transition_digest[:12]}"
    baseline_action = f"action-before-{transition_digest[:12]}"
    runtime.proof.add(ProofNode(baseline_source, "SOURCE", "sanitized provider baseline readback", TruthState.VERIFIED, confidence=1.0))
    runtime.proof.add(ProofNode(baseline_prop, "PROPOSITION", f"current provider status is {before.observed_status}", TruthState.VERIFIED, confidence=1.0, depends_on=[baseline_source]))
    runtime.proof.add(ProofNode(baseline_action, "ACTION", "dependent work based on the baseline may proceed while baseline remains current", TruthState.INFERENCE, confidence=0.8, depends_on=[baseline_prop]))
    mission.nodes["baseline_observe"].status = NodeState.DONE
    ready_after_baseline = sorted(node.node_id for node in runtime.missions.ready_nodes(mission_id))

    after_event = FederationEvent(
        event_id=f"EVT-AFTER-{transition_digest[:16]}",
        event_type="NEW_EVIDENCE",
        source=str(payload["provider"]),
        workstream="AO-HARMONIC-V3-OPERATIONAL-TRANSITION",
        idempotency_key=f"{transition_digest}:after",
        timestamp=after.observed_at,
        proof_class="PROVIDER_READBACK",
        authority_class=str(payload.get("authority_ceiling", "A1_READ")),
        affected_state_keys=(state_key,),
        affected_mission_nodes=("change_observe", "dependent_internal"),
        payload={"phase": "after", "status": after.observed_status, "result_count": after.result_count},
    )
    after_actions = runtime.events.emit(after_event)
    runtime.state.append_event(state_key, {"event_id": after_event.event_id, "phase": "after", "status": after.observed_status, "observed_at": after.observed_at})
    runtime.state.project(state_key, value=after.observed_status, source=f"{payload['provider']}:{payload['capability']}", verified_at=after.observed_at, status="VERIFIED")
    runtime.state.interpret(state_key, meaning="provider state changed; stale baseline must no longer control dependent work", owner_system="JARVIS_ASSURANCE_MESH", basis=[before_event.event_id, after_event.event_id], version="AO-HARMONIC-V3-OPERATIONAL-1")

    impacted = runtime.proof.downgrade(baseline_prop, new_status=TruthState.CONTRADICTED, confidence=0.0)
    for node in impacted:
        node.verification_status = TruthState.CONTRADICTED
        node.confidence = 0.0

    after_source = f"source-after-{transition_digest[:12]}"
    after_prop = f"proposition-after-{transition_digest[:12]}"
    after_action = f"action-after-{transition_digest[:12]}"
    runtime.proof.add(ProofNode(after_source, "SOURCE", "sanitized provider changed-state readback", TruthState.VERIFIED, confidence=1.0))
    runtime.proof.add(ProofNode(after_prop, "PROPOSITION", f"current provider status is {after.observed_status}", TruthState.VERIFIED, confidence=1.0, depends_on=[after_source]))
    runtime.proof.add(ProofNode(after_action, "ACTION", "dependent internal work may proceed on the changed provider state", TruthState.INFERENCE, confidence=0.9, depends_on=[after_prop]))

    mission.nodes["change_observe"].status = NodeState.DONE
    ready_after_change = sorted(node.node_id for node in runtime.missions.ready_nodes(mission_id))
    state = runtime.state.get(state_key)
    state_changed = bool(state and state.current_projection.get("value") == after.observed_status and before.observed_status != after.observed_status)
    history_preserved = bool(state and [evt.get("phase") for evt in state.immutable_events] == ["before", "after"])
    proof_propagated = (
        runtime.proof.nodes[baseline_prop].verification_status == TruthState.CONTRADICTED
        and runtime.proof.nodes[baseline_action].verification_status == TruthState.CONTRADICTED
        and runtime.proof.nodes[after_prop].verification_status == TruthState.VERIFIED
    )
    jarvis = runtime.jarvis.audit_transition(intended_execution=True, provider_dependent=True, readback_present=True, state_changed=state_changed)

    operational_candidate = (
        state_changed
        and history_preserved
        and proof_propagated
        and not jarvis["hold"]
        and "dependent_internal" in ready_after_change
        and "unrelated_internal" in ready_after_change
        and "dependent_internal" not in ready_after_baseline
        and len(payload["prior_workflow_receipt_sha256"]) >= 2
    )

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "capsule_id": payload["capsule_id"],
        "capsule_sha256": transition_digest,
        "provider_runtime": provider_runtime,
        "observed_provider_class": str(payload["provider"]),
        "capability": str(payload["capability"]),
        "authority_ceiling": str(payload.get("authority_ceiling", "A1_READ")),
        "privacy_model": payload["privacy_model"],
        "external_effect": False,
        "provider_mutation_caused_by_runtime": False,
        "real_provider_state_change_observed": state_changed,
        "immutable_event_history_preserved": history_preserved,
        "proof_impact_propagated": proof_propagated,
        "mission_recomputed": operational_candidate,
        "before_status": before.observed_status,
        "after_status": after.observed_status,
        "before_event_actions": before_actions,
        "after_event_actions": after_actions,
        "ready_after_baseline": ready_after_baseline,
        "ready_after_change": ready_after_change,
        "prior_workflow_cycle_count": len(payload["prior_workflow_receipt_sha256"]),
        "prior_workflow_receipt_sha256": list(payload["prior_workflow_receipt_sha256"]),
        "jarvis_defects": list(jarvis["defects"]),
        "workflow_status": "PASS" if operational_candidate else "HOLD",
        "maturity_candidate": "OPERATIONAL_VERIFIED_PENDING_INDEPENDENT_POST_RUNTIME_PROVIDER_READBACK" if operational_candidate else "WORKFLOW_VERIFIED",
        "truth_boundary": {
            "package_runtime_executed_in_github_actions": operational_candidate,
            "provider_state_change_was_real_and_observed": state_changed,
            "provider_mutation_was_caused_by_ao_harmonic_runtime": False,
            "independent_post_runtime_provider_readback_pending": True,
            "operationally_verified": False,
            "global_operational_verification": False,
            "authority_expansion": False,
        },
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    return receipt
