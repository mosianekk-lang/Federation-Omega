"""Closed Pydantic contracts for metadata-only heartbeat HTTP traffic."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from evidenceops.capability_heartbeat.foundation.contracts import (
    Authority,
    BlockerCode,
    CapabilityStatus,
    NodeState,
)
from evidenceops.capability_heartbeat.foundation.privacy import reject_sensitive_tree

from .errors import MetadataBoundaryViolation

CODE = re.compile(r"[A-Z][A-Z0-9_.:-]{2,63}")
HASH = re.compile(r"sha256:[0-9a-f]{64}")
SAFE_DIGEST = re.compile(r"(?:sha256|hmac-sha256):[0-9a-f]{64}")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
RESOURCE_ID = re.compile(r"(?:emitter/[A-Z][A-Z0-9_.:-]{2,63}|heartbeat/sha256:[0-9a-f]{64})")
OBJECT_KEY = re.compile(r"(?:events|receipts)/[0-9a-f]{64}\.json")
SAFE_INTERNAL_KEYS = frozenset({"live_master_bible_attachment"})


def reject_metadata_tree(value: Any, *, path: str) -> None:
    """Apply the foundation privacy gate without misclassifying typed digests as phone numbers."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key not in SAFE_INTERNAL_KEYS:
                reject_sensitive_tree({key: "SAFE"}, path=path)
            reject_metadata_tree(child, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            reject_metadata_tree(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and (
        SAFE_DIGEST.fullmatch(value) is not None
        or UTC.fullmatch(value) is not None
        or CODE.fullmatch(value) is not None
        or RESOURCE_ID.fullmatch(value) is not None
        or OBJECT_KEY.fullmatch(value) is not None
    ):
        return
    reject_sensitive_tree(value, path=path)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class MetadataRequest(StrictModel):
    """Request-only privacy gate; responses contain already-verified signed hashes."""

    @model_validator(mode="after")
    def enforce_metadata_only(self):
        reject_metadata_tree(self.model_dump(mode="json"), path="$request")
        return self


class ResourceKind(str, Enum):
    ALL = "ALL"
    EMITTER = "EMITTER"
    HEARTBEAT = "HEARTBEAT"


class ObservationInput(MetadataRequest):
    source_code: Literal["LOCAL_BIBLE", "LOCAL_REPO", "FORMATION_STATE"]
    node_id: str = Field(pattern=r"^NODE-[A-Z0-9]{1,32}(?:-[0-9]{1,8})?$")
    capability_code: str = Field(pattern=r"^(?:CAP|CAPABILITY)-[A-Z0-9]{1,40}$")
    status: CapabilityStatus
    confidence_bp: int = Field(ge=0, le=10_000)
    freshness_seconds: int = Field(ge=0, le=86_400)
    evidence_count: int = Field(ge=0, le=1_000_000)
    blocker_code: BlockerCode
    capability_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observed_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    semantic_receipt: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class IngestRequest(MetadataRequest):
    idempotency_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    trace_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_transaction_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    mission_code: str = Field(pattern=r"^MISSION-[A-F0-9]{8}$")
    emitter_node_id: str = Field(pattern=r"^NODE-[A-Z0-9]{1,32}(?:-[0-9]{1,8})?$")
    authority_ceiling: Literal[Authority.A0] = Authority.A0
    state: NodeState = NodeState.NEEDS_CAPABILITY
    observed_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    expires_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    sequence: int = Field(ge=0, le=9_223_372_036_854_775_807)
    observations: tuple[ObservationInput, ...] = Field(min_length=1, max_length=32)

    @field_validator("observations")
    @classmethod
    def unique_observations(cls, value: tuple[ObservationInput, ...]) -> tuple[ObservationInput, ...]:
        identities = tuple((item.source_code, item.capability_hash, item.semantic_receipt) for item in value)
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate observations are prohibited")
        return value


class SearchRequest(MetadataRequest):
    resource_kind: ResourceKind = ResourceKind.ALL
    emitter_node_id: str | None = Field(
        default=None,
        pattern=r"^NODE-[A-Z0-9]{1,32}(?:-[0-9]{1,8})?$",
    )
    authority_ceiling: Literal[Authority.A0] = Authority.A0
    offset: int = Field(default=0, ge=0, le=1_000_000)
    limit: int = Field(default=20, ge=1, le=100)


class HealthResponse(StrictModel):
    ok: bool
    service_code: Literal["EVIDENCEOPS-HEARTBEAT-API"]
    schema_version: Literal["HEARTBEAT-HTTP-0.1"]


class ReadinessResponse(StrictModel):
    ready: bool
    mode: Literal["development", "production"]
    authority_ready: bool
    authentication_ready: bool
    signer_material_injected: bool
    store_ready: bool
    external_durability_ready: bool
    provider_registry_proven: bool
    provider_storage_proven: bool
    reasons: tuple[str, ...]


class ResourceSummary(StrictModel):
    resource_id: str = Field(pattern=r"^(?:emitter/[A-Z][A-Z0-9_.:-]{2,63}|heartbeat/sha256:[0-9a-f]{64})$")
    resource_kind: Literal["EMITTER", "HEARTBEAT"]
    emitter_node_id: str = Field(pattern=r"^NODE-[A-Z0-9]{1,32}(?:-[0-9]{1,8})?$")
    authority_ceiling: Literal[Authority.A0]
    state_code: str = Field(pattern=r"^[A-Z][A-Z0-9_.:-]{2,63}$")
    observed_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    semantic_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SearchResponse(StrictModel):
    results: tuple[ResourceSummary, ...]
    offset: int
    next_offset: int | None
    total: int


class FetchResponse(StrictModel):
    resource: dict[str, object]
    semantic_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class IngestResponse(StrictModel):
    resource_id: str = Field(pattern=r"^heartbeat/sha256:[0-9a-f]{64}$")
    idempotency_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    envelope_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    receipt_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    object_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_ceiling: Literal[Authority.A0]
    created: bool
    replayed: bool


def validate_resource_id(value: str) -> str:
    if not isinstance(value, str) or RESOURCE_ID.fullmatch(value) is None:
        raise MetadataBoundaryViolation("invalid metadata resource identifier")
    return value
