"""Signed pull-path propagation with freshness, scope, loop, and stop fences."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta

from .contracts import (
    FUTURE_SKEW_SECONDS,
    MAX_HOPS,
    MAX_OBSERVATION_AGE_SECONDS,
    Authority,
    BlockerCode,
    Classification,
    HeartbeatEnvelope,
    NodeState,
    Recommendation,
    SCHEMA_VERSION,
    digest,
    parse_utc,
)
from .errors import ContractError, FreshnessError, ReplayError
from .registry import CLASSIFICATION_RANK, NodeRecord, NodeRegistry
from .signing import RuntimeSigner
from .stop_control import StopControl

ZERO_SIGNATURE = "hmac-sha256:" + "0" * 64


def build_envelope(
    *,
    signer: RuntimeSigner,
    trace_id: str,
    origin_node_id: str,
    root_transaction_id: str,
    mission_code: str,
    owner_code: str,
    matter_code: str,
    classification: Classification,
    state: NodeState,
    capability_hashes: tuple[str, ...],
    blocker_codes: tuple[BlockerCode, ...],
    recommendations: tuple[Recommendation, ...],
    observed_at: str,
    expires_at: str,
    sequence: int,
    control_generation: int,
) -> HeartbeatEnvelope:
    placeholder = "sha256:" + "0" * 64
    provisional = HeartbeatEnvelope(
        schema_version=SCHEMA_VERSION,
        envelope_id=placeholder,
        trace_id=trace_id,
        origin_node_id=origin_node_id,
        signing_node_id=origin_node_id,
        signer_identity=signer.identity,
        parent_envelope_id=None,
        root_transaction_id=root_transaction_id,
        mission_code=mission_code,
        owner_code=owner_code,
        matter_code=matter_code,
        classification=classification,
        state=state,
        capability_hashes=capability_hashes,
        blocker_codes=blocker_codes,
        recommendations=recommendations,
        observed_at=observed_at,
        expires_at=expires_at,
        sequence=sequence,
        hop_count=0,
        control_generation=control_generation,
        visited_node_ids=(origin_node_id,),
        delegation_ceiling=Authority.A0,
        idempotency_key=placeholder,
        signature=ZERO_SIGNATURE,
    )
    idempotency_key = digest(provisional.identity_body())
    envelope_id = digest(
        {
            "kind": "HEARTBEAT_ENVELOPE",
            "idempotency_key": idempotency_key,
            "trace_id": trace_id,
            "sequence": sequence,
        }
    )
    return signer.sign_envelope(
        replace(
            provisional,
            envelope_id=envelope_id,
            idempotency_key=idempotency_key,
        )
    )


def verify_identity(envelope: HeartbeatEnvelope) -> None:
    expected_idempotency = digest(envelope.identity_body())
    if envelope.idempotency_key != expected_idempotency:
        raise ReplayError("IDEMPOTENCY_BINDING_MISMATCH")
    expected_envelope_id = digest(
        {
            "kind": "HEARTBEAT_ENVELOPE",
            "idempotency_key": envelope.idempotency_key,
            "trace_id": envelope.trace_id,
            "sequence": envelope.sequence,
        }
    )
    if envelope.envelope_id != expected_envelope_id:
        raise ReplayError("ENVELOPE_ID_BINDING_MISMATCH")


def _assert_freshness(envelope: HeartbeatEnvelope, *, now: str) -> None:
    current = parse_utc(now, field="now")
    observed = parse_utc(envelope.observed_at, field="observed_at")
    expires = parse_utc(envelope.expires_at, field="expires_at")
    if observed > current + timedelta(seconds=FUTURE_SKEW_SECONDS):
        raise FreshnessError("ENVELOPE_FUTURE_DATED")
    if expires <= current:
        raise FreshnessError("ENVELOPE_EXPIRED")
    if (current - observed).total_seconds() > MAX_OBSERVATION_AGE_SECONDS:
        raise FreshnessError("ENVELOPE_STALE")


def _assert_classification(envelope: HeartbeatEnvelope, record: NodeRecord) -> None:
    if CLASSIFICATION_RANK[envelope.classification] < CLASSIFICATION_RANK[record.classification]:
        raise ContractError("ENVELOPE_CLASSIFICATION_WEAKER_THAN_NODE")


def _verify_lineage(
    *,
    lineage: tuple[HeartbeatEnvelope, ...],
    registry: NodeRegistry,
    stop_control: StopControl,
    runtime_verifiers: Mapping[str, RuntimeSigner],
    now: str,
) -> tuple[HeartbeatEnvelope, tuple[NodeRecord, ...]]:
    if not isinstance(lineage, tuple) or not 1 <= len(lineage) <= MAX_HOPS + 1:
        raise ContractError("COMPLETE_ENVELOPE_LINEAGE_REQUIRED")
    if any(not isinstance(item, HeartbeatEnvelope) for item in lineage):
        raise ContractError("ENVELOPE_LINEAGE_ITEM_REQUIRED")
    if not isinstance(runtime_verifiers, Mapping):
        raise ContractError("RUNTIME_VERIFIER_MAPPING_REQUIRED")
    root_semantic_hash = digest(lineage[0].lineage_semantic_body())
    records: list[NodeRecord] = []
    for index, envelope in enumerate(lineage):
        verify_identity(envelope)
        _assert_freshness(envelope, now=now)
        stop_control.assert_current(envelope.control_generation)
        if envelope.hop_count != index or len(envelope.visited_node_ids) != index + 1:
            raise ContractError("LINEAGE_HOP_SEQUENCE_MISMATCH")
        if index == 0:
            if envelope.parent_envelope_id is not None:
                raise ContractError("LINEAGE_ROOT_PARENT_PROHIBITED")
        else:
            parent = lineage[index - 1]
            if envelope.parent_envelope_id != parent.envelope_id:
                raise ContractError("LINEAGE_PARENT_ENVELOPE_MISMATCH")
            if envelope.sequence != parent.sequence + 1:
                raise ContractError("LINEAGE_SEQUENCE_MISMATCH")
            expected_path = parent.visited_node_ids + (envelope.signing_node_id,)
            if envelope.visited_node_ids != expected_path:
                raise ContractError("LINEAGE_PATH_PREFIX_MISMATCH")
            if digest(envelope.lineage_semantic_body()) != root_semantic_hash:
                raise ContractError("LINEAGE_SEMANTIC_PAYLOAD_MUTATION")
        record = registry.assert_fresh(envelope.signing_node_id, now=now)
        records.append(record)
        if record.control_generation != envelope.control_generation:
            raise ContractError("NODE_CONTROL_GENERATION_MISMATCH")
        if record.owner_code != envelope.owner_code or record.matter_code != envelope.matter_code:
            raise ContractError("CROSS_OWNER_OR_MATTER_BLEED")
        _assert_classification(envelope, record)
        if index > 0 and record.parent_node_id != records[index - 1].node_id:
            raise ContractError("VISITED_PARENT_CHAIN_MISMATCH")
        verifier = runtime_verifiers.get(envelope.signing_node_id)
        if not isinstance(verifier, RuntimeSigner):
            raise ContractError("REGISTERED_LINEAGE_VERIFIER_REQUIRED")
        verifier.verify_envelope(envelope, node_record=record, stop_control=stop_control)
    expected_visited = tuple(item.signing_node_id for item in lineage)
    current = lineage[-1]
    if current.visited_node_ids != expected_visited:
        raise ContractError("COMPLETE_LINEAGE_PATH_MISMATCH")
    if current.hop_count != len(lineage) - 1:
        raise ContractError("INCOMPLETE_ENVELOPE_LINEAGE")
    return current, tuple(records)


def _verify_route(
    *,
    lineage: tuple[HeartbeatEnvelope, ...],
    destination_node_id: str,
    registry: NodeRegistry,
    stop_control: StopControl,
    runtime_verifiers: Mapping[str, RuntimeSigner],
    now: str,
) -> tuple[HeartbeatEnvelope, NodeRecord, NodeRecord]:
    envelope, visited_records = _verify_lineage(
        lineage=lineage,
        registry=registry,
        stop_control=stop_control,
        runtime_verifiers=runtime_verifiers,
        now=now,
    )
    origin = visited_records[0]
    current_signer = visited_records[-1]
    if origin.node_id != envelope.origin_node_id or current_signer.node_id != envelope.signing_node_id:
        raise ContractError("ENVELOPE_PATH_ENDPOINT_MISMATCH")
    destination = registry.assert_fresh(destination_node_id, now=now)
    if destination_node_id in envelope.visited_node_ids:
        raise ReplayError("PROPAGATION_LOOP_DETECTED")
    if destination.parent_node_id != current_signer.node_id:
        raise ContractError("DESTINATION_PARENT_CHAIN_MISMATCH")
    if destination.control_generation != envelope.control_generation:
        raise ContractError("NODE_CONTROL_GENERATION_MISMATCH")
    if destination.owner_code != envelope.owner_code or destination.matter_code != envelope.matter_code:
        raise ContractError("CROSS_OWNER_OR_MATTER_BLEED")
    _assert_classification(envelope, destination)
    return envelope, current_signer, destination


def accept_envelope(
    *,
    lineage: tuple[HeartbeatEnvelope, ...],
    destination_node_id: str,
    registry: NodeRegistry,
    stop_control: StopControl,
    runtime_verifiers: Mapping[str, RuntimeSigner],
    destination_signer: RuntimeSigner,
    now: str,
):
    envelope, _, destination = _verify_route(
        lineage=lineage,
        destination_node_id=destination_node_id,
        registry=registry,
        stop_control=stop_control,
        runtime_verifiers=runtime_verifiers,
        now=now,
    )
    destination_signer.assert_binding(
        node_record=destination,
        stop_control=stop_control,
    )
    return destination_signer.make_receipt(
        envelope=envelope,
        accepting_record=destination,
        stop_control=stop_control,
        accepted_at=now,
    )


def forward_envelope(
    *,
    lineage: tuple[HeartbeatEnvelope, ...],
    forwarding_node_id: str,
    registry: NodeRegistry,
    stop_control: StopControl,
    runtime_verifiers: Mapping[str, RuntimeSigner],
    forwarding_signer: RuntimeSigner,
    now: str,
) -> HeartbeatEnvelope:
    envelope = lineage[-1] if lineage else None
    if not isinstance(envelope, HeartbeatEnvelope):
        raise ContractError("COMPLETE_ENVELOPE_LINEAGE_REQUIRED")
    if envelope.hop_count >= MAX_HOPS:
        raise ContractError("HOP_LIMIT_REACHED")
    envelope, _, forwarding_record = _verify_route(
        lineage=lineage,
        destination_node_id=forwarding_node_id,
        registry=registry,
        stop_control=stop_control,
        runtime_verifiers=runtime_verifiers,
        now=now,
    )
    forwarding_signer.assert_binding(
        node_record=forwarding_record,
        stop_control=stop_control,
    )
    provisional = replace(
        envelope,
        envelope_id="sha256:" + "0" * 64,
        parent_envelope_id=envelope.envelope_id,
        signing_node_id=forwarding_node_id,
        signer_identity=forwarding_signer.identity,
        sequence=envelope.sequence + 1,
        hop_count=envelope.hop_count + 1,
        visited_node_ids=envelope.visited_node_ids + (forwarding_node_id,),
        idempotency_key="sha256:" + "0" * 64,
        signature=ZERO_SIGNATURE,
    )
    idempotency_key = digest(provisional.identity_body())
    envelope_id = digest(
        {
            "kind": "HEARTBEAT_ENVELOPE",
            "idempotency_key": idempotency_key,
            "trace_id": envelope.trace_id,
            "sequence": provisional.sequence,
        }
    )
    return forwarding_signer.sign_envelope(
        replace(provisional, envelope_id=envelope_id, idempotency_key=idempotency_key)
    )
