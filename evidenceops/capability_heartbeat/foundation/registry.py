"""Immutable node registry with owner, matter, generation, and inheritance fences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import (
    Authority,
    Classification,
    NodeType,
    SignerIdentity,
    SUPPORTED_SIGNING_VERSIONS,
    canonicalize,
    digest,
    enum_value,
    parse_utc,
    validate_common_codes,
)
from .errors import AuthorityError, ContractError, FreshnessError, HeartbeatError, ReplayError
from .privacy import require_code, require_hash

AUTHORITY_RANK = {authority: index for index, authority in enumerate(Authority)}
CLASSIFICATION_RANK = {
    Classification.PUBLIC_META: 0,
    Classification.INTERNAL_META: 1,
    Classification.RESTRICTED_META: 2,
}


@dataclass(frozen=True, slots=True)
class NodeRecord:
    node_id: str
    node_type: NodeType
    parent_node_id: str | None
    generation: int
    owner_code: str
    matter_code: str
    classification: Classification
    schema_version: str
    adapter_version: str
    capability_hash: str
    authority_ceiling: Authority
    observed_at: str
    expires_at: str
    control_generation: int
    endpoint_reference_hash: str
    signer_identity: SignerIdentity
    registration_receipt: str

    def __post_init__(self) -> None:
        validate_common_codes(node_id=self.node_id, owner_code=self.owner_code, matter_code=self.matter_code)
        object.__setattr__(self, "node_type", enum_value(NodeType, self.node_type, field="node_type"))
        object.__setattr__(self, "classification", enum_value(Classification, self.classification, field="classification"))
        object.__setattr__(self, "authority_ceiling", enum_value(Authority, self.authority_ceiling, field="authority_ceiling"))
        if self.parent_node_id is not None:
            require_code(self.parent_node_id, field="parent_node_id")
        for field_name in ("schema_version", "adapter_version"):
            require_code(getattr(self, field_name), field=field_name)
        if not isinstance(self.signer_identity, SignerIdentity):
            raise ContractError("SIGNER_IDENTITY_REQUIRED")
        for field_name in ("capability_hash", "endpoint_reference_hash", "registration_receipt"):
            require_hash(getattr(self, field_name), field=field_name)
        observed = parse_utc(self.observed_at, field="observed_at")
        expires = parse_utc(self.expires_at, field="expires_at")
        if expires <= observed:
            raise ContractError("NODE_EXPIRY_MUST_FOLLOW_OBSERVATION")
        for field_name in ("generation", "control_generation"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ContractError(f"INVALID_NONNEGATIVE_INTEGER:{field_name}")
        if self.signer_identity.rotation_generation != self.control_generation:
            raise ContractError("SIGNER_CONTROL_GENERATION_MISMATCH")
        if self.node_type is NodeType.MASTER_BIBLE and self.parent_node_id is not None:
            raise ContractError("MASTER_BIBLE_CANNOT_HAVE_PARENT")
        if self.node_type is not NodeType.MASTER_BIBLE and self.parent_node_id is None:
            raise ContractError("CHILD_PARENT_REQUIRED")

    @property
    def record_hash(self) -> str:
        return digest(canonicalize(self))


@dataclass(frozen=True, slots=True)
class NodeRegistry:
    records: tuple[NodeRecord, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.records, (tuple, list)):
            raise ContractError("REGISTRY_RECORDS_SEQUENCE_REQUIRED")
        snapshot = tuple(self.records)
        if any(not isinstance(item, NodeRecord) for item in snapshot):
            raise ContractError("REGISTRY_RECORD_ITEM_REQUIRED")
        object.__setattr__(self, "records", snapshot)

    @property
    def registry_hash(self) -> str:
        return digest([canonicalize(item) for item in sorted(self.records, key=lambda item: item.node_id)])

    def get(self, node_id: str) -> NodeRecord:
        require_code(node_id, field="node_id")
        matches = [item for item in self.records if item.node_id == node_id]
        if not matches:
            raise ContractError("NODE_NOT_REGISTERED")
        return matches[0]

    def register(self, record: NodeRecord) -> "NodeRegistry":
        existing = [item for item in self.records if item.node_id == record.node_id]
        if existing:
            if existing[0] == record:
                return self
            raise ReplayError("NODE_REGISTRATION_CONFLICT")
        if not self.records:
            if record.node_type is not NodeType.MASTER_BIBLE:
                raise ContractError("FIRST_NODE_MUST_BE_MASTER_BIBLE")
            if record.authority_ceiling is not Authority.A0:
                raise AuthorityError("MASTER_BIBLE_HEARTBEAT_CEILING_MUST_BE_A0")
            if record.signer_identity.signing_version not in SUPPORTED_SIGNING_VERSIONS:
                raise ContractError("UNSUPPORTED_ROOT_SIGNING_VERSION")
        else:
            if record.parent_node_id is None:
                raise ContractError("CHILD_PARENT_REQUIRED")
            parent = self.get(record.parent_node_id)
            if record.owner_code != parent.owner_code or record.matter_code != parent.matter_code:
                raise ContractError("CROSS_OWNER_OR_MATTER_REGISTRATION")
            if record.control_generation != parent.control_generation:
                raise ContractError("CONTROL_GENERATION_INHERITANCE_MISMATCH")
            if record.generation != parent.generation + 1:
                raise ContractError("NODE_GENERATION_MUST_INCREMENT")
            if record.schema_version != parent.schema_version:
                raise ContractError("SCHEMA_VERSION_INHERITANCE_MISMATCH")
            if record.adapter_version != parent.adapter_version:
                raise ContractError("ADAPTER_VERSION_INHERITANCE_MISMATCH")
            if record.signer_identity.signing_version != parent.signer_identity.signing_version:
                raise ContractError("SIGNING_VERSION_INHERITANCE_MISMATCH")
            if AUTHORITY_RANK[record.authority_ceiling] > AUTHORITY_RANK[parent.authority_ceiling]:
                raise AuthorityError("CHILD_AUTHORITY_WIDENING_PROHIBITED")
            if CLASSIFICATION_RANK[record.classification] < CLASSIFICATION_RANK[parent.classification]:
                raise AuthorityError("CHILD_CLASSIFICATION_WEAKENING_PROHIBITED")
        return NodeRegistry(self.records + (record,))

    def assert_fresh(self, node_id: str, *, now: str) -> NodeRecord:
        record = self.get(node_id)
        current = parse_utc(now, field="now")
        observed = parse_utc(record.observed_at, field="observed_at")
        expires = parse_utc(record.expires_at, field="expires_at")
        if observed > current or expires <= current:
            raise FreshnessError("NODE_REGISTRATION_NOT_FRESH")
        return record

    def semantic_readback(self) -> dict[str, Any]:
        roots = [item.node_id for item in self.records if item.node_type is NodeType.MASTER_BIBLE]
        valid = len(roots) == 1 if self.records else False
        if valid:
            try:
                rebuilt = NodeRegistry()
                for item in sorted(self.records, key=lambda value: value.generation):
                    rebuilt = rebuilt.register(item)
                valid = rebuilt.registry_hash == self.registry_hash
            except HeartbeatError:
                valid = False
        return {
            "valid": valid,
            "node_count": len(self.records),
            "root_node_ids": tuple(roots),
            "registry_hash": self.registry_hash,
        }
