from __future__ import annotations

import hashlib

from evidenceops.capability_heartbeat.foundation.contracts import (
    Authority,
    BlockerCode,
    CapabilityStatus,
    Classification,
    EventType,
    NodeState,
    NodeType,
    digest,
)
from evidenceops.capability_heartbeat.foundation.ledger import ImmutableEventLedger
from evidenceops.capability_heartbeat.foundation.master_bible import MasterBiblePolicy
from evidenceops.capability_heartbeat.foundation.propagation import build_envelope
from evidenceops.capability_heartbeat.foundation.registry import NodeRegistry
from evidenceops.capability_heartbeat.foundation.scoring import CapabilityCandidate, select_recommendations
from evidenceops.capability_heartbeat.foundation.signing import RuntimeSigner
from evidenceops.capability_heartbeat.foundation.stop_control import StopControl

OBSERVED = "2026-08-02T12:00:00Z"
NOW = "2026-08-02T12:00:10Z"
EXPIRES = "2026-08-02T12:10:00Z"
OWNER = "OWNER-A1B2C3D4"
MATTER = "MATTER-B1C2D3E4"
MISSION = "MISSION-C1D2E3F4"
ROOT_TX = digest({"transaction": "ROOT"})
TRACE = digest({"trace": "TRACE"})


def hash_of(code: str) -> str:
    return digest({"code": code})


def node_signer(
    node_id: str,
    *,
    rotation_generation: int = 0,
    material_code: str = "LEGITIMATE",
    key_id: str | None = None,
    signing_version: str = "HMAC-0.1",
) -> RuntimeSigner:
    key = hashlib.sha256(
        f"TEST-ONLY|{node_id}|{rotation_generation}|{material_code}".encode("ascii")
    ).digest()
    return RuntimeSigner(
        key,
        node_id=node_id,
        key_id=key_id or f"KEY-{node_id}",
        signing_version=signing_version,
        rotation_generation=rotation_generation,
    )


def signer(*, rotation_generation: int = 0, material_code: str = "LEGITIMATE") -> RuntimeSigner:
    return node_signer(
        "NODE-ROOT",
        rotation_generation=rotation_generation,
        material_code=material_code,
    )


def candidate(
    code: str,
    confidence: int = 9000,
    *,
    status: CapabilityStatus = CapabilityStatus.AVAILABLE,
    blocker: BlockerCode = BlockerCode.NONE,
    compatible: bool = True,
) -> CapabilityCandidate:
    return CapabilityCandidate(
        capability_code=code,
        status=status,
        confidence_bp=confidence,
        freshness_seconds=10,
        evidence_count=3,
        compatible=compatible,
        blocker_code=blocker,
    )


def registry_with_chain(count: int = 4, *, control_generation: int = 0, material_code: str = "LEGITIMATE"):
    policy = MasterBiblePolicy.create(
        root_node_id="NODE-ROOT",
        owner_code=OWNER,
        matter_code=MATTER,
        classification=Classification.INTERNAL_META,
        control_generation=control_generation,
    )
    root = policy.root_record(
        observed_at=OBSERVED,
        expires_at=EXPIRES,
        capability_hash=hash_of("ROOT-CAP"),
        endpoint_reference_hash=hash_of("ROOT-ENDPOINT"),
        registration_receipt=hash_of("ROOT-RECEIPT"),
        signer_identity=signer(
            rotation_generation=control_generation,
            material_code=material_code,
        ).identity,
    )
    registry = NodeRegistry().register(root)
    parent = root
    nodes = [root]
    for index in range(1, count):
        child = policy.inherit_child(
            registry=registry,
            parent_node_id=parent.node_id,
            child_node_id=f"NODE-CHILD-{index}",
            node_type=NodeType.BIBLE_NODE if index == 1 else NodeType.AGENT_SPAWN,
            observed_at=OBSERVED,
            expires_at=EXPIRES,
            capability_hash=hash_of(f"CAP-{index}"),
            endpoint_reference_hash=hash_of(f"ENDPOINT-{index}"),
            registration_receipt=hash_of(f"RECEIPT-{index}"),
            signer_identity=node_signer(
                f"NODE-CHILD-{index}",
                rotation_generation=control_generation,
                material_code=material_code,
            ).identity,
        )
        registry = registry.register(child)
        nodes.append(child)
        parent = child
    return policy, registry, tuple(nodes)


def envelope(
    *,
    recommendations=None,
    observed_at=OBSERVED,
    expires_at=EXPIRES,
    control_generation: int = 0,
    runtime_signer: RuntimeSigner | None = None,
    classification: Classification = Classification.INTERNAL_META,
):
    selected = recommendations
    if selected is None:
        selected = select_recommendations((candidate("CAPABILITY-A"),))
    return build_envelope(
        signer=runtime_signer or signer(rotation_generation=control_generation),
        trace_id=TRACE,
        origin_node_id="NODE-ROOT",
        root_transaction_id=ROOT_TX,
        mission_code=MISSION,
        owner_code=OWNER,
        matter_code=MATTER,
        classification=classification,
        state=NodeState.NEEDS_CAPABILITY,
        capability_hashes=(hash_of("CAPABILITY-A"),),
        blocker_codes=(),
        recommendations=selected,
        observed_at=observed_at,
        expires_at=expires_at,
        sequence=1,
        control_generation=control_generation,
    )


def ledger() -> ImmutableEventLedger:
    return ImmutableEventLedger().append(
        event_type=EventType.NODE_REGISTERED,
        entity_code="NODE-ROOT",
        occurred_at=OBSERVED,
        control_generation=0,
        payload={"node_code": "NODE-ROOT", "state_code": "REGISTERED"},
    )


def stop_control() -> StopControl:
    return StopControl()
