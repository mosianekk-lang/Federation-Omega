"""Bounded no-effect real-mission control-state shadow for AO-HARMONIC v3.

The fixture intentionally contains no private case facts, message bodies, names,
credentials, legal conclusions, or provider mutations. It models only the
structural state observed in a real mission: two externally waiting lanes, two
independent internal preparation lanes, several candidate resource routes, and
an owner-interruption decision.

A passing shadow validates these source primitives for this bounded scenario.
It does not establish provider deployment, provider effects, legal accuracy,
or Federation-wide operational maturity.
"""

from __future__ import annotations

from .models import (
    Maturity,
    Mission,
    MissionNode,
    NodeState,
    ProofNode,
    ResourceOffer,
    RiskClass,
    TruthState,
)
from .resource_market import ResourceRequest
from .runtime import AOHarmonicV3


SHADOW_ID = "AO-HARMONIC-V3-REAL-MISSION-CONTROL-SHADOW-001"


def run_control_state_shadow() -> dict[str, object]:
    runtime = AOHarmonicV3()

    mission = Mission(
        mission_id="MISSION-SHADOW-001",
        objective="maintain readiness while external decisions remain pending",
        desired_outcome="continue all safe independent preparation",
        risk_class=RiskClass.HIGH,
        authority_ceiling="A1_INTERNAL",
    )
    runtime.missions.add_mission(mission)

    for node in (
        MissionNode("external_reply", "await external reply"),
        MissionNode("external_ruling", "await external ruling"),
        MissionNode("evidence_prepare", "continue evidence preparation"),
        MissionNode("fallback_prepare", "continue fallback preparation"),
    ):
        runtime.missions.add_node(mission.mission_id, node)

    runtime.missions.block_node(mission.mission_id, "external_reply", "EXTERNAL_WAIT")
    runtime.missions.block_node(mission.mission_id, "external_ruling", "EXTERNAL_WAIT")

    ready_nodes = runtime.missions.ready_nodes(mission.mission_id)
    blocked_nodes = [
        node
        for node in runtime.missions.missions[mission.mission_id].nodes.values()
        if node.status == NodeState.BLOCKED
    ]

    resources = [
        ResourceOffer(
            resource_id="gmail-live",
            provider="Gmail",
            capability="SEARCH_EMAIL",
            semantic_scope="provider-native-mail live current-response search",
            authority_ceiling="A1_READ",
            maturity=Maturity.OPERATIONAL_VERIFIED,
            relevance=1.0,
            semantic_fit=1.0,
            freshness=1.0,
            reliability=0.98,
            proof_strength=0.95,
            executability=1.0,
            information_gain=0.95,
            latency=0.5,
            owner_burden=0.0,
            privacy_cost=0.2,
            duplication_cost=0.1,
            failure_risk=0.1,
        ),
        ResourceOffer(
            resource_id="drive-archive",
            provider="Google Drive",
            capability="SEARCH_EMAIL",
            semantic_scope="archived-mail derivative search",
            authority_ceiling="A1_READ",
            maturity=Maturity.WORKFLOW_VERIFIED,
            relevance=0.65,
            semantic_fit=0.55,
            freshness=0.45,
            reliability=0.9,
            proof_strength=0.6,
            executability=1.0,
            information_gain=0.45,
            latency=1.0,
            owner_burden=0.0,
            privacy_cost=0.2,
            duplication_cost=0.5,
            failure_risk=0.2,
        ),
    ]
    request = ResourceRequest(
        capability="SEARCH_EMAIL",
        semantic_scope="provider-native-mail",
        minimum_maturity=Maturity.DETERMINISTIC_TESTED,
        maximum_owner_burden=0.0,
    )
    selected = runtime.resources.best(resources, request)

    attention_score = runtime.attention.score(
        urgency=0.4,
        consequence=0.5,
        decision_necessity=0.2,
        owner_exclusivity=0.1,
        self_resolution_capability=0.95,
    )
    owner_interrupt = runtime.attention.should_interrupt(attention_score)

    runtime.proof.add(
        ProofNode(
            "source-current",
            "SOURCE",
            "current provider source",
            TruthState.VERIFIED,
            confidence=1.0,
        )
    )
    runtime.proof.add(
        ProofNode(
            "proposition-current",
            "PROPOSITION",
            "current state proposition",
            TruthState.VERIFIED,
            confidence=0.9,
            depends_on=["source-current"],
        )
    )
    runtime.proof.add(
        ProofNode(
            "action-current",
            "ACTION",
            "dependent internal action",
            TruthState.INFERENCE,
            confidence=0.7,
            depends_on=["proposition-current"],
        )
    )
    affected = runtime.proof.downgrade(
        "source-current",
        new_status=TruthState.CONTRADICTED,
        confidence=0.1,
    )

    return {
        "shadow_id": SHADOW_ID,
        "truth_boundary": "REAL_MISSION_DERIVED_CONTROL_STATE_NO_PRIVATE_PAYLOAD_NO_EXTERNAL_EFFECT",
        "external_effect": False,
        "authority_ceiling": "A1_INTERNAL",
        "blocked_external_lanes": len(blocked_nodes),
        "independent_ready_lanes": len(ready_nodes),
        "ready_node_ids": sorted(node.node_id for node in ready_nodes),
        "selected_resource": selected.resource_id if selected else None,
        "owner_interrupt": owner_interrupt,
        "proof_dependants_reached": sorted(node.proof_node_id for node in affected),
        "formal_scope": "AO_HARMONIC_V3_SYSTEM_SPECIFIC_NO_EFFECT_SHADOW",
    }
