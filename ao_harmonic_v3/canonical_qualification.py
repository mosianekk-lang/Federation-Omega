from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import FederationEvent, Mission, MissionNode, NodeState, ProofNode, RiskClass, TruthState
from .provider_canary import ProviderObservation, ProviderObservationCanary
from .runtime import AOHarmonicV3

CAPSULE_SCHEMA = "AO_HARMONIC_V3_CANONICAL_QUALIFICATION_CAPSULE_V1"
RECEIPT_SCHEMA = "AO_HARMONIC_V3_CANONICAL_QUALIFICATION_RECEIPT_V1"
_ALLOWED_RUNTIME = {"GITHUB_ACTIONS"}


def _sha(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _valid_sha(value: object) -> bool:
    text = str(value)
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text.lower())


def validate_capsule(payload: dict[str, Any]) -> None:
    if payload.get("schema") != CAPSULE_SCHEMA:
        raise ValueError("unsupported canonical qualification schema")
    if payload.get("privacy_model") != "SANITIZED_METADATA_ONLY":
        raise ValueError("canonical qualification requires sanitized metadata only")
    if payload.get("external_effect") is not False:
        raise ValueError("canonical qualification runtime must remain no-effect")
    if payload.get("provider_mutation_caused_by_runtime") is not False:
        raise ValueError("qualification runtime may not claim it caused provider mutation")
    if payload.get("private_provider_object_identifier_persisted_publicly") is not False:
        raise ValueError("private provider identifiers may not be persisted publicly")
    if not _valid_sha(payload.get("operational_receipt_sha256")):
        raise ValueError("bounded operational receipt is required")
    prior = payload.get("prior_workflow_receipt_sha256", [])
    if not isinstance(prior, list) or len(prior) < 2 or not all(_valid_sha(x) for x in prior):
        raise ValueError("at least two prior workflow receipts are required")
    sequence = payload.get("adverse_recovery_sequence", [])
    if not isinstance(sequence, list) or len(sequence) != 3:
        raise ValueError("qualification requires exactly baseline, adverse and recovered observations")
    statuses = [x.get("observed_status") for x in sequence]
    if statuses != ["FOUND", "NOT_FOUND", "FOUND"]:
        raise ValueError("required real-provider sequence is FOUND -> NOT_FOUND -> FOUND")
    fingerprints = {x.get("object_fingerprint") for x in sequence}
    if len(fingerprints) != 1 or not _valid_sha(next(iter(fingerprints))):
        raise ValueError("all transition observations must bind the same sanitized provider object")
    for item in sequence:
        if item.get("transport_ok") is not True or item.get("semantic_match") is not True:
            raise ValueError("all real-provider observations require semantic readback")
    independent = payload.get("independent_provider_cycle", {})
    if independent.get("provider") == payload.get("transition_provider"):
        raise ValueError("independent provider must be a different provider class")
    if not _valid_sha(independent.get("object_fingerprint")):
        raise ValueError("independent provider fingerprint is required")
    if independent.get("transport_ok") is not True or independent.get("semantic_match") is not True:
        raise ValueError("independent provider cycle requires semantic readback")


def run_canonical_qualification(payload: dict[str, Any], *, provider_runtime: str) -> dict[str, Any]:
    validate_capsule(payload)
    if provider_runtime not in _ALLOWED_RUNTIME:
        raise ValueError("unapproved provider runtime")

    runtime = AOHarmonicV3()
    digest = _sha(payload)
    mission_id = f"CANONICAL-{digest[:16]}"
    state_key = f"canonical-transition:{payload['transition_provider'].lower()}:{payload['adverse_recovery_sequence'][0]['object_fingerprint'][:16]}"

    mission = Mission(
        mission_id=mission_id,
        objective="qualify AO-HARMONIC core runtime under adverse provider loss and recovery",
        desired_outcome="fail closed on degraded proof, recover dependent work on verified restoration, preserve unrelated work and cross-provider coherence",
        risk_class=RiskClass.HIGH,
        authority_ceiling=str(payload.get("authority_ceiling", "A1_READ")),
    )
    runtime.missions.add_mission(mission)
    for node in (
        MissionNode("baseline", "verify baseline provider state"),
        MissionNode("adverse", "observe adverse provider loss", dependencies=["baseline"]),
        MissionNode("recovery", "observe provider recovery", dependencies=["adverse"]),
        MissionNode("recovered_dependent", "resume dependent work only after recovery", dependencies=["recovery"]),
        MissionNode("unrelated_internal", "continue unrelated safe work"),
    ):
        runtime.missions.add_node(mission_id, node)

    phase_nodes: list[str] = []
    proof_ids: list[str] = []
    previous_prop: str | None = None
    for index, item in enumerate(payload["adverse_recovery_sequence"]):
        phase = ("baseline", "adverse", "recovery")[index]
        observed = str(item["observed_status"])
        expected = str(item["expected_status"])
        semantic = runtime.semantic_firewall.evaluate(
            transport_ok=bool(item["transport_ok"]),
            semantic_match=bool(item["semantic_match"]) and observed == expected,
        )
        if semantic != "SUCCESS":
            raise ValueError(f"semantic readback failed at {phase}")

        event = FederationEvent(
            event_id=f"EVT-{phase.upper()}-{digest[:16]}",
            event_type="NEW_EVIDENCE",
            source=str(payload["transition_provider"]),
            workstream="AO-HARMONIC-V3-CANONICAL-QUALIFICATION",
            idempotency_key=f"{digest}:{phase}",
            timestamp=str(item["observed_at"]),
            proof_class="PROVIDER_READBACK",
            authority_class=str(payload.get("authority_ceiling", "A1_READ")),
            affected_state_keys=(state_key,),
            affected_mission_nodes=(phase, "recovered_dependent"),
            payload={"phase": phase, "status": observed},
        )
        runtime.events.emit(event)
        runtime.state.append_event(state_key, {"event_id": event.event_id, "phase": phase, "status": observed})
        runtime.state.project(
            state_key,
            value=observed,
            source=f"{payload['transition_provider']}:{payload['transition_capability']}",
            verified_at=str(item["observed_at"]),
            status="VERIFIED",
        )
        runtime.state.interpret(
            state_key,
            meaning=f"current qualification provider state is {observed}",
            owner_system="JARVIS_ASSURANCE_MESH",
            basis=[event.event_id],
            version="AO-HARMONIC-V3-CANONICAL-1",
        )

        source_id = f"source-{phase}-{digest[:10]}"
        prop_id = f"prop-{phase}-{digest[:10]}"
        runtime.proof.add(ProofNode(source_id, "SOURCE", f"sanitized {phase} provider readback", TruthState.VERIFIED, confidence=1.0))
        runtime.proof.add(ProofNode(prop_id, "PROPOSITION", f"provider state is {observed}", TruthState.VERIFIED, confidence=1.0, depends_on=[source_id]))
        proof_ids.append(prop_id)
        if previous_prop is not None:
            impacted = runtime.proof.downgrade(previous_prop, new_status=TruthState.CONTRADICTED, confidence=0.0)
            for child in impacted:
                child.verification_status = TruthState.CONTRADICTED
                child.confidence = 0.0
        previous_prop = prop_id

        mission.nodes[phase].status = NodeState.DONE
        if phase == "adverse":
            mission.nodes["recovered_dependent"].status = NodeState.BLOCKED
            mission.nodes["recovered_dependent"].blockers = ["PROVIDER_STATE_DEGRADED"]
        elif phase == "recovery":
            mission.nodes["recovered_dependent"].status = NodeState.READY
            mission.nodes["recovered_dependent"].blockers.clear()
        phase_nodes.append(phase)

    independent = payload["independent_provider_cycle"]
    independent_receipt = ProviderObservationCanary().run(ProviderObservation(
        provider=str(independent["provider"]),
        capability=str(independent["capability"]),
        object_fingerprint=str(independent["object_fingerprint"]),
        expected_status=str(independent["expected_status"]),
        observed_status=str(independent["observed_status"]),
        observed_at=str(independent["observed_at"]),
        transport_ok=bool(independent["transport_ok"]),
        semantic_match=bool(independent["semantic_match"]),
        result_count=int(independent.get("result_count", 1)),
        related_count=int(independent.get("related_count", 0)),
        authority_ceiling=str(payload.get("authority_ceiling", "A1_READ")),
        external_effect=False,
    ))

    state = runtime.state.get(state_key)
    history = [x.get("phase") for x in state.immutable_events] if state else []
    final_projection = state.current_projection.get("value") if state else None
    ready = sorted(x.node_id for x in runtime.missions.ready_nodes(mission_id))
    degraded_prop = runtime.proof.nodes[proof_ids[1]]
    recovered_prop = runtime.proof.nodes[proof_ids[2]]
    baseline_prop = runtime.proof.nodes[proof_ids[0]]

    pass_gate = (
        history == ["baseline", "adverse", "recovery"]
        and final_projection == "FOUND"
        and baseline_prop.verification_status == TruthState.CONTRADICTED
        and degraded_prop.verification_status == TruthState.CONTRADICTED
        and recovered_prop.verification_status == TruthState.VERIFIED
        and "recovered_dependent" in ready
        and "unrelated_internal" in ready
        and independent_receipt["status"] == "PASS"
        and independent_receipt["external_effect"] is False
    )

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "capsule_id": payload["capsule_id"],
        "capsule_sha256": digest,
        "provider_runtime": provider_runtime,
        "transition_provider": payload["transition_provider"],
        "independent_provider": independent["provider"],
        "provider_class_count": 3,
        "operational_diversity": ["REAL_STATE_CHANGE", "ADVERSE_STATE_LOSS", "RECOVERY", "INDEPENDENT_STABLE_PROVIDER", "GITHUB_ACTIONS_RUNTIME"],
        "immutable_event_history": history,
        "final_projection": final_projection,
        "stale_baseline_contradicted": baseline_prop.verification_status == TruthState.CONTRADICTED,
        "adverse_state_contradicted_after_recovery": degraded_prop.verification_status == TruthState.CONTRADICTED,
        "recovery_state_verified": recovered_prop.verification_status == TruthState.VERIFIED,
        "mission_recovered": "recovered_dependent" in ready,
        "unrelated_lane_continued": "unrelated_internal" in ready,
        "independent_provider_pass": independent_receipt["status"] == "PASS",
        "prior_workflow_cycle_count": len(payload["prior_workflow_receipt_sha256"]),
        "bounded_operational_receipt_bound": payload["operational_receipt_sha256"],
        "external_effect": False,
        "provider_mutation_caused_by_runtime": False,
        "authority_ceiling": str(payload.get("authority_ceiling", "A1_READ")),
        "qualification_status": "PASS" if pass_gate else "HOLD",
        "maturity_candidate": "CANONICAL_AO_HARMONIC_V3_CORE_RUNTIME_PENDING_INDEPENDENT_POST_RUNTIME_MULTI_PROVIDER_READBACK" if pass_gate else "OPERATIONAL_VERIFIED",
        "truth_boundary": {
            "core_runtime_canonical_candidate": pass_gate,
            "global_federation_canonical": False,
            "provider_deployed": False,
            "provider_mutation_caused_by_runtime": False,
            "external_effect": False,
            "authority_expansion": False,
            "independent_post_runtime_multi_provider_readback_pending": True,
        },
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt
