"""A0-only runtime for metadata ingest, registry discovery, and semantic readback."""

from __future__ import annotations

import base64
import binascii
import hmac
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Mapping

from evidenceops.capability_heartbeat.authority import VerifiedV4Authority
from evidenceops.capability_heartbeat.foundation.adapters.common import Observation
from evidenceops.capability_heartbeat.foundation.contracts import (
    Authority,
    Classification,
    HeartbeatEnvelope,
    NodeType,
    Receipt,
    canonical_json,
    canonicalize,
    digest,
)
from evidenceops.capability_heartbeat.foundation.errors import HeartbeatError
from evidenceops.capability_heartbeat.foundation.master_bible import MasterBiblePolicy
from evidenceops.capability_heartbeat.foundation.registry import NodeRegistry
from evidenceops.capability_heartbeat.foundation.signing import RuntimeSigner
from evidenceops.capability_heartbeat.foundation.privacy import strict_json_loads

from .auth import InternalTokenAuthorizer
from .errors import ImmutableConflict, ResourceNotFound, RuntimeUnavailable
from .schemas import (
    FetchResponse,
    IngestRequest,
    IngestResponse,
    ReadinessResponse,
    ResourceKind,
    ResourceSummary,
    SearchRequest,
    SearchResponse,
    reject_metadata_tree,
    validate_resource_id,
)
from .store import ImmutableObjectStore, InMemoryImmutableStore, LocalImmutableObjectStore, payload_hash

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
EXTERNAL_DURABILITY = "EXTERNAL_IMMUTABLE_OBJECT_STORE"
MAX_REGISTERED_EMITTERS = 1_000


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(UTC_FORMAT)


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    mode: Literal["development", "production"] = "development"
    internal_auth_value: str = field(default="", repr=False)
    signer_material_injected: bool = False
    registry_source_code: str = "UNCONFIGURED"
    accept_node_id: str = "NODE-EVIDENCEOPS"
    provider_authoritative_registry_proven: bool = False
    provider_authoritative_storage_proven: bool = False


class HeartbeatApiRuntime:
    """One policy facade plus one create-only store; no independent policy path."""

    def __init__(
        self,
        *,
        config: RuntimeConfig,
        store: ImmutableObjectStore,
        authority: VerifiedV4Authority | None,
    ) -> None:
        if not isinstance(store, ImmutableObjectStore):
            raise TypeError("immutable object store contract required")
        self.config = config
        self.store = store
        self.authority = authority
        self.authorizer = InternalTokenAuthorizer(config.internal_auth_value)

    def readiness(self, *, now: str | None = None) -> ReadinessResponse:
        observed_now = now or utc_now()
        reasons: list[str] = []
        authority_ready = False
        if self.authority is None:
            reasons.append("AUTHORITY_UNCONFIGURED")
        else:
            try:
                if len(self.authority.registry.records) > MAX_REGISTERED_EMITTERS:
                    raise RuntimeUnavailable("emitter registry capacity exceeded")
                self.authority.stop_control.assert_current(self.authority.policy.control_generation)
                self.authority.authority_readback(now=observed_now)
                self.authority.registry.get(self.config.accept_node_id)
                authority_ready = True
            except HeartbeatError:
                reasons.append("AUTHORITY_READBACK_FAILED")
        authentication_ready = self.authorizer.configured
        if not authentication_ready:
            reasons.append("INTERNAL_AUTH_UNCONFIGURED")
        if not self.config.signer_material_injected:
            reasons.append("SIGNER_MATERIAL_NOT_INJECTED")
        health = self.store.health()
        store_ready = health.get("healthy") is True
        if not store_ready:
            reasons.append("IMMUTABLE_STORE_UNHEALTHY")
        external_durability_ready = self.store.durability_class == EXTERNAL_DURABILITY
        if self.config.mode == "production" and not external_durability_ready:
            reasons.append("EXTERNAL_IMMUTABLE_STORE_REQUIRED")
        if self.config.mode == "production" and not self.config.provider_authoritative_registry_proven:
            reasons.append("PROVIDER_REGISTRY_PROOF_REQUIRED")
        if self.config.mode == "production" and not self.config.provider_authoritative_storage_proven:
            reasons.append("PROVIDER_STORAGE_PROOF_REQUIRED")
        ready = all(
            (
                authority_ready,
                authentication_ready,
                self.config.signer_material_injected,
                store_ready,
                self.config.mode != "production" or external_durability_ready,
                self.config.mode != "production" or self.config.provider_authoritative_registry_proven,
                self.config.mode != "production" or self.config.provider_authoritative_storage_proven,
            )
        )
        return ReadinessResponse(
            ready=ready,
            mode=self.config.mode,
            authority_ready=authority_ready,
            authentication_ready=authentication_ready,
            signer_material_injected=self.config.signer_material_injected,
            store_ready=store_ready,
            external_durability_ready=external_durability_ready,
            provider_registry_proven=self.config.provider_authoritative_registry_proven,
            provider_storage_proven=self.config.provider_authoritative_storage_proven,
            reasons=tuple(reasons),
        )

    def require_ready(self, *, now: str | None = None) -> VerifiedV4Authority:
        state = self.readiness(now=now)
        if not state.ready or self.authority is None:
            raise RuntimeUnavailable("heartbeat API is not ready")
        return self.authority

    def status(self, *, now: str | None = None) -> dict[str, object]:
        state = self.readiness(now=now)
        authority_readback: dict[str, object] | None = None
        if state.authority_ready and self.authority is not None:
            authority_readback = self.authority.authority_readback(now=now or utc_now())
        result = {
            "schema": "EVIDENCEOPS-HEARTBEAT-API-STATUS-0.1",
            "maturity": "IMPLEMENTED_NOT_DEPLOYED",
            "authority_ceiling": Authority.A0.value,
            "recommendation_only": True,
            "ready": state.ready,
            "readiness_reasons": list(state.reasons),
            "registry_source_code": self.config.registry_source_code,
            "store": self.store.health(),
            "authority": authority_readback,
            "live_awareness_flags": (
                self.authority.live_awareness_flags if self.authority is not None else {
                    "live_master_bible_attachment": False,
                    "active_chat_inventory": False,
                    "per_chat_emitters": False,
                    "unsolicited_injection": False,
                    "system_wide_awareness": False,
                }
            ),
        }
        reject_metadata_tree(result, path="$status")
        return result

    @staticmethod
    def _event_key(idempotency_hash: str) -> str:
        return "events/" + idempotency_hash.removeprefix("sha256:") + ".json"

    @staticmethod
    def _resource_index_key(envelope_id: str) -> str:
        return "receipts/" + envelope_id.removeprefix("sha256:") + ".json"

    @staticmethod
    def _decode_event(value: bytes) -> dict[str, object]:
        try:
            decoded = strict_json_loads(value.decode("utf-8"), field="stored_event")
        except (UnicodeDecodeError, HeartbeatError) as exc:
            raise RuntimeUnavailable("stored event is not canonical JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeUnavailable("stored event is not an object")
        reject_metadata_tree(decoded, path="$stored_event")
        return decoded

    @staticmethod
    def _verify_event(event: Mapping[str, object], authority: VerifiedV4Authority) -> None:
        try:
            envelope_value = event["envelope"]
            receipt_value = event["receipt"]
            if not isinstance(envelope_value, dict) or not isinstance(receipt_value, dict):
                raise RuntimeUnavailable("signed event contracts missing")
            envelope = HeartbeatEnvelope.from_mapping(envelope_value)
            receipt = Receipt.from_mapping(receipt_value)
            origin_record = authority.registry.get(envelope.signing_node_id)
            destination_record = authority.registry.get(receipt.accepting_node_id)
            authority.verifier_for(envelope.signing_node_id).verify_envelope(
                envelope,
                node_record=origin_record,
                stop_control=authority.stop_control,
            )
            authority.verifier_for(receipt.accepting_node_id).verify_receipt(
                receipt,
                accepted_envelope=envelope,
                destination_record=destination_record,
                stop_control=authority.stop_control,
                now=str(event["accepted_at"]),
            )
            checks = (
                event.get("resource_id") == "heartbeat/" + envelope.envelope_id,
                event.get("envelope_id") == envelope.envelope_id,
                event.get("receipt_id") == receipt.receipt_id,
                event.get("semantic_hash") == receipt.semantic_hash,
                event.get("emitter_node_id") == authority.policy.root_node_id,
                event.get("accepting_node_id") == receipt.accepting_node_id,
                event.get("authority_ceiling") == Authority.A0.value,
            )
            if not all(checks):
                raise RuntimeUnavailable("signed event readback mismatch")
        except (KeyError, TypeError, HeartbeatError) as exc:
            raise RuntimeUnavailable("signed event verification failed") from exc

    def _event_for_idempotency(self, idempotency_hash: str) -> tuple[dict[str, object], str]:
        stored = self.store.read(self._event_key(idempotency_hash))
        if payload_hash(stored.value) != stored.object_hash:
            raise RuntimeUnavailable("stored event object hash mismatch")
        event = self._decode_event(stored.value)
        if event.get("idempotency_hash") != idempotency_hash:
            raise RuntimeUnavailable("immutable event key binding mismatch")
        return event, stored.object_hash

    def _ensure_resource_index(self, event: Mapping[str, object], *, object_hash: str) -> None:
        envelope_id = str(event["envelope_id"])
        index = {
            "schema": "EVIDENCEOPS-HEARTBEAT-RESOURCE-INDEX-0.1",
            "resource_id": event["resource_id"],
            "envelope_id": envelope_id,
            "idempotency_hash": event["idempotency_hash"],
            "event_key": self._event_key(str(event["idempotency_hash"])),
            "event_object_hash": object_hash,
        }
        reject_metadata_tree(index, path="$resource_index")
        encoded = canonical_json(index).encode("utf-8")
        stored, _created = self.store.create_if_absent(self._resource_index_key(envelope_id), encoded)
        persisted = self._decode_event(stored.value)
        if persisted != index:
            raise ImmutableConflict("resource index conflict")

    def _event_for_resource(self, resource_id: str) -> tuple[dict[str, object], str]:
        envelope_id = resource_id.removeprefix("heartbeat/")
        index_object = self.store.read(self._resource_index_key(envelope_id))
        index = self._decode_event(index_object.value)
        expected_index = {
            "resource_id": resource_id,
            "envelope_id": envelope_id,
        }
        if any(index.get(key) != value for key, value in expected_index.items()):
            raise RuntimeUnavailable("resource index binding mismatch")
        idempotency_hash = index.get("idempotency_hash")
        event_key = index.get("event_key")
        if not isinstance(idempotency_hash, str) or event_key != self._event_key(idempotency_hash):
            raise RuntimeUnavailable("resource index event binding mismatch")
        event, object_hash = self._event_for_idempotency(idempotency_hash)
        if object_hash != index.get("event_object_hash") or event.get("resource_id") != resource_id:
            raise RuntimeUnavailable("resource index object binding mismatch")
        return event, object_hash

    @staticmethod
    def _response_from_event(
        event: Mapping[str, object],
        *,
        object_hash: str,
        created: bool,
    ) -> IngestResponse:
        return IngestResponse(
            resource_id=str(event["resource_id"]),
            idempotency_hash=str(event["idempotency_hash"]),
            envelope_id=str(event["envelope_id"]),
            receipt_id=str(event["receipt_id"]),
            object_hash=object_hash,
            authority_ceiling=Authority.A0,
            created=created,
            replayed=not created,
        )

    def ingest(self, request: IngestRequest, *, accepted_at: str | None = None) -> IngestResponse:
        authority = self.require_ready(now=accepted_at or utc_now())
        body = request.model_dump(mode="json")
        reject_metadata_tree(body, path="$ingest")
        request_hash = digest({"schema": "HEARTBEAT-INGEST-REQUEST-0.1", "body": body})
        try:
            existing, object_hash = self._event_for_idempotency(request.idempotency_hash)
        except ResourceNotFound:
            existing = None
        if existing is not None:
            self._verify_event(existing, authority)
            if existing.get("request_hash") != request_hash:
                raise ImmutableConflict("idempotency hash was reused for a different request")
            self._ensure_resource_index(existing, object_hash=object_hash)
            return self._response_from_event(existing, object_hash=object_hash, created=False)

        if request.authority_ceiling is not Authority.A0:
            raise RuntimeUnavailable("heartbeat authority widening denied")
        if request.emitter_node_id != authority.policy.root_node_id:
            raise RuntimeUnavailable("only the verified root emitter can originate ingest envelopes")
        for item in request.observations:
            authority.registry.assert_fresh(item.node_id, now=accepted_at or utc_now())
        observations = tuple(
            Observation(
                source_code=item.source_code,
                node_id=item.node_id,
                owner_code=authority.policy.owner_code,
                matter_code=authority.policy.matter_code,
                capability_code=item.capability_code,
                status=item.status,
                confidence_bp=item.confidence_bp,
                freshness_seconds=item.freshness_seconds,
                evidence_count=item.evidence_count,
                blocker_code=item.blocker_code,
                capability_hash=item.capability_hash,
                observed_at=item.observed_at,
                semantic_receipt=item.semantic_receipt,
            )
            for item in request.observations
        )
        result, envelope = authority.build_root_envelope(
            observations=observations,
            now=accepted_at or utc_now(),
            expires_at=request.expires_at,
            trace_id=request.trace_id,
            root_transaction_id=request.root_transaction_id,
            mission_code=request.mission_code,
            sequence=request.sequence,
            state=request.state,
        )
        receipt = authority.accept(
            lineage=(envelope,),
            destination_node_id=self.config.accept_node_id,
            now=accepted_at or utc_now(),
        )
        resource_id = "heartbeat/" + envelope.envelope_id
        event = {
            "schema": "EVIDENCEOPS-HEARTBEAT-IMMUTABLE-EVENT-0.1",
            "resource_id": resource_id,
            "resource_kind": "HEARTBEAT",
            "idempotency_hash": request.idempotency_hash,
            "request_hash": request_hash,
            "emitter_node_id": request.emitter_node_id,
            "accepting_node_id": self.config.accept_node_id,
            "authority_ceiling": Authority.A0.value,
            "observed_at": request.observed_at,
            "accepted_at": accepted_at or utc_now(),
            "state_code": request.state.value,
            "input_digest": result.input_digest,
            "envelope_id": envelope.envelope_id,
            "receipt_id": receipt.receipt_id,
            "semantic_hash": receipt.semantic_hash,
            "envelope": canonicalize(envelope),
            "receipt": canonicalize(receipt),
        }
        reject_metadata_tree(event, path="$event")
        encoded = canonical_json(event).encode("utf-8")
        stored, created = self.store.create_if_absent(self._event_key(request.idempotency_hash), encoded)
        if not created:
            persisted = self._decode_event(stored.value)
            if persisted.get("request_hash") != request_hash:
                raise ImmutableConflict("concurrent immutable request conflict")
            event = persisted
        self._ensure_resource_index(event, object_hash=stored.object_hash)
        return self._response_from_event(event, object_hash=stored.object_hash, created=created)

    def readback(self, idempotency_hash: str, *, now: str | None = None) -> dict[str, object]:
        authority = self.require_ready(now=now or utc_now())
        event, object_hash = self._event_for_idempotency(idempotency_hash)
        self._verify_event(event, authority)
        semantic_hash = digest(
            {
                "resource_id": event.get("resource_id"),
                "envelope_id": event.get("envelope_id"),
                "receipt_id": event.get("receipt_id"),
                "request_hash": event.get("request_hash"),
                "object_hash": object_hash,
            }
        )
        return {
            "schema": "EVIDENCEOPS-HEARTBEAT-READBACK-0.1",
            "verified": True,
            "resource_id": event["resource_id"],
            "idempotency_hash": event["idempotency_hash"],
            "envelope_id": event["envelope_id"],
            "receipt_id": event["receipt_id"],
            "object_hash": object_hash,
            "semantic_hash": semantic_hash,
            "authority_ceiling": Authority.A0.value,
        }

    def _emitter_summaries(self, *, now: str) -> tuple[ResourceSummary, ...]:
        authority = self.require_ready(now=now)
        return tuple(
            ResourceSummary(
                resource_id="emitter/" + record.node_id,
                resource_kind="EMITTER",
                emitter_node_id=record.node_id,
                authority_ceiling=Authority.A0,
                state_code="REGISTERED",
                observed_at=record.observed_at,
                semantic_hash=record.record_hash,
            )
            for record in sorted(authority.registry.records, key=lambda item: item.node_id)
        )

    def _heartbeat_summaries(
        self,
        authority: VerifiedV4Authority,
        *,
        offset: int,
        limit: int,
    ) -> tuple[tuple[ResourceSummary, ...], int]:
        summaries: list[ResourceSummary] = []
        page = self.store.page_prefix("events/", offset=offset, limit=limit)
        for stored in page.objects:
            event = self._decode_event(stored.value)
            if event.get("idempotency_hash") != "sha256:" + stored.key.removeprefix("events/").removesuffix(".json"):
                raise RuntimeUnavailable("paged event key binding mismatch")
            self._verify_event(event, authority)
            summaries.append(
                ResourceSummary(
                    resource_id=str(event["resource_id"]),
                    resource_kind="HEARTBEAT",
                    emitter_node_id=str(event["emitter_node_id"]),
                    authority_ceiling=Authority.A0,
                    state_code=str(event["state_code"]),
                    observed_at=str(event["observed_at"]),
                    semantic_hash=str(event["semantic_hash"]),
                )
            )
        return tuple(summaries), page.total

    def search(self, request: SearchRequest, *, now: str | None = None) -> SearchResponse:
        observed_now = now or utc_now()
        authority = self.require_ready(now=observed_now)
        emitters = self._emitter_summaries(now=observed_now)
        if request.emitter_node_id is not None:
            emitters = tuple(item for item in emitters if item.emitter_node_id == request.emitter_node_id)
        heartbeat_allowed = request.emitter_node_id in {None, authority.policy.root_node_id}

        results: tuple[ResourceSummary, ...] = ()
        total = 0
        if request.resource_kind is ResourceKind.EMITTER:
            total = len(emitters)
            results = emitters[request.offset : request.offset + request.limit]
        elif request.resource_kind is ResourceKind.HEARTBEAT:
            if heartbeat_allowed:
                results, total = self._heartbeat_summaries(
                    authority,
                    offset=request.offset,
                    limit=request.limit,
                )
        else:
            emitter_total = len(emitters)
            if request.offset < emitter_total:
                emitter_page = emitters[request.offset : request.offset + request.limit]
                results += emitter_page
                remaining = request.limit - len(emitter_page)
                event_offset = 0
            else:
                remaining = request.limit
                event_offset = request.offset - emitter_total
            event_total = 0
            if heartbeat_allowed:
                event_page, event_total = self._heartbeat_summaries(
                    authority,
                    offset=event_offset,
                    limit=max(1, remaining),
                )
                if remaining:
                    results += event_page[:remaining]
            total = emitter_total + event_total
        next_offset = request.offset + len(results) if request.offset + len(results) < total else None
        return SearchResponse(results=results, offset=request.offset, next_offset=next_offset, total=total)

    def fetch(self, resource_id: str, *, now: str | None = None) -> FetchResponse:
        resource_id = validate_resource_id(resource_id)
        observed_now = now or utc_now()
        authority = self.require_ready(now=observed_now)
        if resource_id.startswith("emitter/"):
            node_id = resource_id.removeprefix("emitter/")
            record = authority.registry.assert_fresh(node_id, now=observed_now)
            value = {
                "schema": "EVIDENCEOPS-EMITTER-READ-MODEL-0.1",
                "resource_id": resource_id,
                "resource_kind": "EMITTER",
                "node_id": record.node_id,
                "node_type": record.node_type.value,
                "parent_node_id": record.parent_node_id,
                "generation": record.generation,
                "classification": record.classification.value,
                "authority_ceiling": record.authority_ceiling.value,
                "observed_at": record.observed_at,
                "expires_at": record.expires_at,
                "control_generation": record.control_generation,
                "capability_hash": record.capability_hash,
                "record_hash": record.record_hash,
                "can_originate_ingest": record.node_id == authority.policy.root_node_id,
            }
            reject_metadata_tree(value, path="$emitter")
            return FetchResponse(resource=value, semantic_hash=record.record_hash)
        event, _object_hash = self._event_for_resource(resource_id)
        self._verify_event(event, authority)
        return FetchResponse(resource=event, semantic_hash=str(event["semantic_hash"]))


def _decode_signer_material(value: str) -> bytes:
    try:
        material = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeUnavailable("invalid encoded signer material") from exc
    if len(material) < 32:
        raise RuntimeUnavailable("signer material is too short")
    return material


def _configured_authority(environment: Mapping[str, str], *, now: datetime) -> tuple[VerifiedV4Authority, str]:
    root_node_id = environment["HEARTBEAT_ROOT_NODE_ID"]
    accept_node_id = environment["HEARTBEAT_ACCEPT_NODE_ID"]
    owner_code = environment["HEARTBEAT_OWNER_CODE"]
    matter_code = environment["HEARTBEAT_MATTER_CODE"]
    generation = int(environment.get("HEARTBEAT_CONTROL_GENERATION", "0"))
    root_material = _decode_signer_material(environment["HEARTBEAT_ROOT_SIGNER_B64"])
    accept_material = _decode_signer_material(environment["HEARTBEAT_ACCEPT_SIGNER_B64"])
    if hmac.compare_digest(root_material, accept_material):
        raise RuntimeUnavailable("node signer separation required")
    root_signer = RuntimeSigner(
        root_material,
        node_id=root_node_id,
        key_id="KEY-" + root_node_id,
        rotation_generation=generation,
    )
    accept_signer = RuntimeSigner(
        accept_material,
        node_id=accept_node_id,
        key_id="KEY-" + accept_node_id,
        rotation_generation=generation,
    )
    observed_at = (now - timedelta(seconds=1)).strftime(UTC_FORMAT)
    expires_at = (now + timedelta(minutes=30)).strftime(UTC_FORMAT)
    policy = MasterBiblePolicy.create(
        root_node_id=root_node_id,
        owner_code=owner_code,
        matter_code=matter_code,
        classification=Classification.INTERNAL_META,
        control_generation=generation,
    )
    root = policy.root_record(
        observed_at=observed_at,
        expires_at=expires_at,
        capability_hash=digest({"capability": "HEARTBEAT-ROOT"}),
        endpoint_reference_hash=digest({"endpoint": "PRIVATE-HTTP-ADAPTER"}),
        registration_receipt=digest({"registration": "ENVIRONMENT-INJECTED-ROOT", "generation": generation}),
        signer_identity=root_signer.identity,
    )
    registry = NodeRegistry().register(root)
    accept = policy.inherit_child(
        registry=registry,
        parent_node_id=root.node_id,
        child_node_id=accept_node_id,
        node_type=NodeType.SYSTEM_NODE,
        observed_at=observed_at,
        expires_at=expires_at,
        capability_hash=digest({"capability": "HEARTBEAT-ACCEPT"}),
        endpoint_reference_hash=digest({"endpoint": "PRIVATE-HTTP-ADAPTER"}),
        registration_receipt=digest({"registration": "ENVIRONMENT-INJECTED-ACCEPT", "generation": generation}),
        signer_identity=accept_signer.identity,
    )
    registry = registry.register(accept)
    return (
        VerifiedV4Authority(
            policy=policy,
            registry=registry,
            runtime_signers={root.node_id: root_signer, accept.node_id: accept_signer},
        ),
        accept.node_id,
    )


def build_runtime_from_env(environment: Mapping[str, str] | None = None) -> HeartbeatApiRuntime:
    env = dict(os.environ if environment is None else environment)
    requested_mode = env.get("HEARTBEAT_MODE", "development")
    if requested_mode not in {"development", "production"}:
        raise RuntimeUnavailable("invalid heartbeat runtime mode")
    mode: Literal["development", "production"] = requested_mode
    store: ImmutableObjectStore
    if env.get("HEARTBEAT_STORE_DIRECTORY"):
        store = LocalImmutableObjectStore(Path(env["HEARTBEAT_STORE_DIRECTORY"]))
    else:
        store = InMemoryImmutableStore()
    required = (
        "HEARTBEAT_ROOT_NODE_ID",
        "HEARTBEAT_ACCEPT_NODE_ID",
        "HEARTBEAT_OWNER_CODE",
        "HEARTBEAT_MATTER_CODE",
        "HEARTBEAT_ROOT_SIGNER_B64",
        "HEARTBEAT_ACCEPT_SIGNER_B64",
    )
    authority: VerifiedV4Authority | None = None
    accept_node_id = env.get("HEARTBEAT_ACCEPT_NODE_ID", "NODE-EVIDENCEOPS")
    signer_injected = all(env.get(item) for item in required)
    if signer_injected:
        try:
            authority, accept_node_id = _configured_authority(env, now=datetime.now(timezone.utc))
        except (HeartbeatError, KeyError, RuntimeUnavailable, ValueError):
            authority = None
            signer_injected = False
    config = RuntimeConfig(
        mode=mode,
        internal_auth_value=env.get("HEARTBEAT_INTERNAL_AUTH_VALUE", ""),
        signer_material_injected=signer_injected,
        registry_source_code=("ENVIRONMENT_INJECTED_RUNTIME" if authority is not None else "UNCONFIGURED"),
        accept_node_id=accept_node_id,
    )
    return HeartbeatApiRuntime(config=config, store=store, authority=authority)
