from __future__ import annotations

import hashlib

from evidenceops.capability_heartbeat.authority import VerifiedV4Authority
from evidenceops.capability_heartbeat.foundation.adapters.common import Observation
from evidenceops.capability_heartbeat.foundation.contracts import (
    Authority,
    BlockerCode,
    CapabilityStatus,
    Classification,
    NodeType,
    digest,
)
from evidenceops.capability_heartbeat.foundation.master_bible import MasterBiblePolicy
from evidenceops.capability_heartbeat.foundation.registry import NodeRegistry
from evidenceops.capability_heartbeat.foundation.signing import RuntimeSigner

OBSERVED = "2026-08-02T12:00:00Z"
NOW = "2026-08-02T12:00:10Z"
EXPIRES = "2026-08-02T12:10:00Z"
OWNER = "OWNER-A1B2C3D4"
MATTER = "MATTER-B1C2D3E4"
MISSION = "MISSION-C1D2E3F4"
TRACE = digest({"trace": "INTEGRATION"})
ROOT_TX = digest({"transaction": "INTEGRATION"})


def signer(node_id: str, *, generation: int = 0, material: str = "PRIMARY") -> RuntimeSigner:
    key = hashlib.sha256(f"SYNTHETIC|{node_id}|{generation}|{material}".encode("ascii")).digest()
    return RuntimeSigner(
        key,
        node_id=node_id,
        key_id=f"KEY-{node_id}",
        signing_version="HMAC-0.1",
        rotation_generation=generation,
    )


def authority(*, generation: int = 0) -> VerifiedV4Authority:
    policy = MasterBiblePolicy.create(
        root_node_id="NODE-ROOT",
        owner_code=OWNER,
        matter_code=MATTER,
        classification=Classification.INTERNAL_META,
        control_generation=generation,
    )
    root_signer = signer("NODE-ROOT", generation=generation)
    root = policy.root_record(
        observed_at=OBSERVED,
        expires_at=EXPIRES,
        capability_hash=digest({"capability": "ROOT"}),
        endpoint_reference_hash=digest({"endpoint": "ROOT"}),
        registration_receipt=digest({"receipt": "ROOT"}),
        signer_identity=root_signer.identity,
    )
    registry = NodeRegistry().register(root)
    destination_signer = signer("NODE-EVIDENCEOPS", generation=generation)
    destination = policy.inherit_child(
        registry=registry,
        parent_node_id=root.node_id,
        child_node_id="NODE-EVIDENCEOPS",
        node_type=NodeType.SYSTEM_NODE,
        observed_at=OBSERVED,
        expires_at=EXPIRES,
        capability_hash=digest({"capability": "EVIDENCEOPS"}),
        endpoint_reference_hash=digest({"endpoint": "EVIDENCEOPS"}),
        registration_receipt=digest({"receipt": "EVIDENCEOPS"}),
        signer_identity=destination_signer.identity,
        requested_authority=Authority.A0,
    )
    registry = registry.register(destination)
    return VerifiedV4Authority(
        policy=policy,
        registry=registry,
        runtime_signers={"NODE-ROOT": root_signer, "NODE-EVIDENCEOPS": destination_signer},
    )


def observation(*, code: str = "CAP-INDEX", owner_code: str = OWNER) -> Observation:
    return Observation(
        source_code="LOCAL_REPO",
        node_id="NODE-ROOT",
        owner_code=owner_code,
        matter_code=MATTER,
        capability_code=code,
        status=CapabilityStatus.AVAILABLE,
        confidence_bp=9000,
        freshness_seconds=10,
        evidence_count=3,
        blocker_code=BlockerCode.NONE,
        capability_hash=digest({"capability": code}),
        observed_at=OBSERVED,
        semantic_receipt=digest({"receipt": code}),
    )


def envelope(value: VerifiedV4Authority | None = None, *, observed_at: str = OBSERVED):
    active = value or authority()
    result, signed = active.build_root_envelope(
        observations=(observation(),),
        now=observed_at,
        expires_at=EXPIRES,
        trace_id=TRACE,
        root_transaction_id=ROOT_TX,
        mission_code=MISSION,
        sequence=1,
    )
    return active, result, signed
