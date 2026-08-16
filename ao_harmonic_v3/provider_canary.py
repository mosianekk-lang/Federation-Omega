from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .models import (
    FederationEvent,
    Maturity,
    Mission,
    MissionNode,
    NodeState,
    ProofNode,
    RiskClass,
    TruthState,
)
from .runtime import AOHarmonicV3


_ALLOWED_STATUSES = {
    "FOUND",
    "NOT_FOUND",
    "DRAFT",
    "SENT",
    "DELIVERED",
    "FILED",
    "ACCEPTED",
    "RESPONDED",
    "RULED",
    "UNCHANGED",
}


@dataclass(frozen=True)
class ProviderObservation:
    """Sanitized provider readback envelope for a no-effect canary.

    The bridge intentionally accepts only metadata required to test semantic
    readback and dependency propagation. Message bodies, recipients, filenames,
    credentials, medical content, legal submissions, and other private payloads
    do not belong in this object.
    """

    provider: str
    capability: str
    object_fingerprint: str
    expected_status: str
    observed_status: str
    observed_at: str
    transport_ok: bool
    semantic_match: bool
    result_count: int = 1
    related_count: int = 0
    authority_ceiling: str = "A1_READ"
    external_effect: bool = False

    def validate(self) -> None:
        if not self.provider.strip() or not self.capability.strip():
            raise ValueError("provider and capability are required")
        if len(self.object_fingerprint) != 64 or any(
            ch not in "0123456789abcdef" for ch in self.object_fingerprint.lower()
        ):
            raise ValueError("object_fingerprint must be a lowercase SHA-256 hex digest")
        if self.expected_status not in _ALLOWED_STATUSES:
            raise ValueError("unsupported expected_status")
        if self.observed_status not in _ALLOWED_STATUSES:
            raise ValueError("unsupported observed_status")
        if self.authority_ceiling not in {"A0_READ", "A1_READ", "A1_INTERNAL"}:
            raise ValueError("provider canary cannot exceed A1")
        if self.external_effect:
            raise ValueError("provider canary must remain no-effect")
        if self.result_count < 0 or self.related_count < 0:
            raise ValueError("counts must be non-negative")

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProviderObservationCanary:
    """Bind sanitized provider readback to AO-HARMONIC v3 structural controls.

    A passing receipt establishes only a bounded read-only provider-observation
    canary for the orchestration contract. It does not establish provider-native
    deployment of the Python package, workflow verification, or operational
    maturity.
    """

    def __init__(self) -> None:
        self.runtime = AOHarmonicV3()

    def run(self, observation: ProviderObservation) -> dict[str, object]:
        observation.validate()
        digest = observation.digest()
        state_key = f"provider:{observation.provider.lower()}:{digest[:16]}"
        mission_id = f"CANARY-{digest[:16]}"

        mission = Mission(
            mission_id=mission_id,
            objective="validate provider observation propagation without external effect",
            desired_outcome="provider readback updates state, proof and dependent work safely",
            risk_class=RiskClass.MODERATE,
            authority_ceiling=observation.authority_ceiling,
        )
        self.runtime.missions.add_mission(mission)
        self.runtime.missions.add_node(
            mission_id,
            MissionNode("provider_observe", "read provider object and verify semantics"),
        )
        self.runtime.missions.add_node(
            mission_id,
            MissionNode(
                "dependent_internal",
                "continue internal work dependent on verified provider state",
                dependencies=["provider_observe"],
            ),
        )
        self.runtime.missions.add_node(
            mission_id,
            MissionNode("unrelated_internal", "continue independent safe internal work"),
        )

        event = FederationEvent(
            event_id=f"EVT-{digest[:20]}",
            event_type="NEW_EVIDENCE",
            source=observation.provider,
            workstream="AO-HARMONIC-V3-PROVIDER-CANARY",
            idempotency_key=digest,
            timestamp=observation.observed_at,
            proof_class="PROVIDER_READBACK",
            authority_class=observation.authority_ceiling,
            affected_state_keys=(state_key,),
            affected_mission_nodes=("provider_observe", "dependent_internal"),
            payload={
                "capability": observation.capability,
                "expected_status": observation.expected_status,
                "observed_status": observation.observed_status,
                "result_count": observation.result_count,
                "related_count": observation.related_count,
            },
        )
        event_actions = self.runtime.events.emit(event)
        self.runtime.state.append_event(
            state_key,
            {
                "event_id": event.event_id,
                "provider": observation.provider,
                "capability": observation.capability,
                "observation_digest": digest,
                "observed_at": observation.observed_at,
            },
        )

        semantic_result = self.runtime.semantic_firewall.evaluate(
            transport_ok=observation.transport_ok,
            semantic_match=observation.semantic_match,
        )
        semantic_success = (
            semantic_result == "SUCCESS"
            and observation.observed_status == observation.expected_status
        )

        truth_state = TruthState.VERIFIED if semantic_success else TruthState.CONTRADICTED
        confidence = 1.0 if semantic_success else 0.1
        current_status = "VERIFIED" if semantic_success else "CONTRADICTED"

        self.runtime.state.project(
            state_key,
            value=observation.observed_status,
            source=f"{observation.provider}:{observation.capability}",
            verified_at=observation.observed_at,
            status=current_status,
        )
        self.runtime.state.interpret(
            state_key,
            meaning=(
                "provider state is safe to use for dependent internal work"
                if semantic_success
                else "provider state is not safe to promote"
            ),
            owner_system="JARVIS_ASSURANCE_MESH",
            basis=[event.event_id, digest],
            version="AO-HARMONIC-V3-PROVIDER-CANARY-1",
        )

        source_id = f"source-{digest[:12]}"
        proposition_id = f"proposition-{digest[:12]}"
        action_id = f"action-{digest[:12]}"
        self.runtime.proof.add(
            ProofNode(
                source_id,
                "SOURCE",
                "sanitized provider readback",
                truth_state,
                confidence=confidence,
            )
        )
        self.runtime.proof.add(
            ProofNode(
                proposition_id,
                "PROPOSITION",
                "current provider state matches the canary expectation",
                truth_state,
                confidence=confidence,
                depends_on=[source_id],
            )
        )
        self.runtime.proof.add(
            ProofNode(
                action_id,
                "ACTION",
                "dependent internal work may proceed only while provider state is verified",
                TruthState.INFERENCE,
                confidence=0.8 if semantic_success else 0.0,
                depends_on=[proposition_id],
            )
        )

        observe_node = mission.nodes["provider_observe"]
        if semantic_success:
            observe_node.status = NodeState.DONE
        else:
            self.runtime.missions.block_node(mission_id, "provider_observe", "SEMANTIC_READBACK_FAILED")
            self.runtime.missions.block_node(mission_id, "dependent_internal", "PROVIDER_STATE_UNVERIFIED")

        ready_ids = sorted(node.node_id for node in self.runtime.missions.ready_nodes(mission_id))
        state_changed = bool(self.runtime.state.get(state_key).current_projection)
        jarvis = self.runtime.jarvis.audit_transition(
            intended_execution=True,
            provider_dependent=True,
            readback_present=True,
            state_changed=state_changed,
        )

        canary_pass = (
            semantic_success
            and not jarvis["hold"]
            and "dependent_internal" in ready_ids
            and "unrelated_internal" in ready_ids
            and observation.external_effect is False
        )

        return {
            "canary_id": mission_id,
            "observation_digest": digest,
            "provider": observation.provider,
            "capability": observation.capability,
            "semantic_readback": semantic_result,
            "expected_status": observation.expected_status,
            "observed_status": observation.observed_status,
            "event_actions": event_actions,
            "state_projection": self.runtime.state.get(state_key).current_projection,
            "ready_node_ids": ready_ids,
            "jarvis_defects": jarvis["defects"],
            "authority_ceiling": observation.authority_ceiling,
            "external_effect": False,
            "status": "PASS" if canary_pass else "HOLD",
            "maturity": (
                Maturity.CANARY_VALIDATED.value
                if canary_pass
                else Maturity.SHADOW_VALIDATED.value
            ),
            "formal_scope": "AO_HARMONIC_V3_PROVIDER_OBSERVATION_BRIDGE_NO_EFFECT",
            "truth_boundary": {
                "provider_observation_verified": canary_pass,
                "python_package_provider_deployed": False,
                "workflow_verified": False,
                "operationally_verified": False,
                "authority_expansion": False,
            },
        }
