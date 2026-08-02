"""Strict immutable contracts for the capability heartbeat foundation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import MISSING, asdict, dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

from .errors import ContractError
from .privacy import require_code, require_hash, require_timestamp_shape

SCHEMA_VERSION = "HEARTBEAT-0.1"
MATURITY = "DURABLE_FOUNDATION_IMPLEMENTED_NOT_ATTACHED"
SUPPORTED_SIGNING_VERSIONS = frozenset({"HMAC-0.1"})
MAX_HOPS = 3
MAX_TTL_SECONDS = 3600
MAX_OBSERVATION_AGE_SECONDS = 300
FUTURE_SKEW_SECONDS = 30


class Classification(str, Enum):
    PUBLIC_META = "PUBLIC_META"
    INTERNAL_META = "INTERNAL_META"
    RESTRICTED_META = "RESTRICTED_META"


class NodeType(str, Enum):
    MASTER_BIBLE = "MASTER_BIBLE"
    BIBLE_NODE = "BIBLE_NODE"
    CHAT_NODE = "CHAT_NODE"
    SYSTEM_NODE = "SYSTEM_NODE"
    AGENT_SPAWN = "AGENT_SPAWN"


class Authority(str, Enum):
    A0 = "A0"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"


class NodeState(str, Enum):
    IDLE = "IDLE"
    NEEDS_CAPABILITY = "NEEDS_CAPABILITY"
    BLOCKED = "BLOCKED"
    READY = "READY"
    STOPPED = "STOPPED"


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class RecommendationRole(str, Enum):
    PREFERRED = "PREFERRED"
    BACKUP = "BACKUP"
    ESCALATION = "ESCALATION"


class BlockerCode(str, Enum):
    NONE = "NONE"
    CAPABILITY_ABSENT = "CAPABILITY_ABSENT"
    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"
    ATTACHMENT_UNPROVEN = "ATTACHMENT_UNPROVEN"
    INVENTORY_UNAVAILABLE = "INVENTORY_UNAVAILABLE"
    SOURCE_STALE = "SOURCE_STALE"
    SEMANTIC_DRIFT = "SEMANTIC_DRIFT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    RATE_LIMITED = "RATE_LIMITED"
    STOP_FENCED = "STOP_FENCED"


class EventType(str, Enum):
    NODE_REGISTERED = "NODE_REGISTERED"
    ENVELOPE_ACCEPTED = "ENVELOPE_ACCEPTED"
    RECOMMENDATION_EMITTED = "RECOMMENDATION_EMITTED"
    RECEIPT_RECORDED = "RECEIPT_RECORDED"
    STOP_GENERATION_ADVANCED = "STOP_GENERATION_ADVANCED"
    RESPAWN_VERIFIED = "RESPAWN_VERIFIED"


T = TypeVar("T", bound=Enum)


def enum_value(enum_type: type[T], value: str | T, *, field: str) -> T:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"UNKNOWN_ENUM:{field}") from exc


def parse_utc(value: str, *, field: str) -> datetime:
    require_timestamp_shape(value, field=field)
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo != timezone.utc:
        raise ContractError(f"UTC_REQUIRED:{field}")
    return parsed


def canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: canonicalize(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): canonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def strict_mapping(cls: type[Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError(f"OBJECT_REQUIRED:{cls.__name__}")
    allowed = {item.name for item in fields(cls)}
    unknown = sorted(set(payload) - allowed)
    missing = sorted(
        item.name
        for item in fields(cls)
        if item.default is MISSING and item.default_factory is MISSING and item.name not in payload
    )
    if unknown:
        raise ContractError(f"UNKNOWN_FIELDS:{cls.__name__}:" + ",".join(unknown))
    if missing:
        raise ContractError(f"MISSING_FIELDS:{cls.__name__}:" + ",".join(missing))
    return dict(payload)


def validate_common_codes(*, node_id: str, owner_code: str, matter_code: str) -> None:
    require_code(node_id, field="node_id")
    require_code(owner_code, field="owner_code")
    require_code(matter_code, field="matter_code")


def validate_digest_sequence(values: tuple[str, ...], *, field: str) -> None:
    if not isinstance(values, tuple) or len(values) > 32 or len(set(values)) != len(values):
        raise ContractError(f"INVALID_DIGEST_SEQUENCE:{field}")
    for value in values:
        require_hash(value, field=field)


@dataclass(frozen=True, slots=True)
class Recommendation:
    role: RecommendationRole
    capability_code: str
    score: int
    blocker_code: BlockerCode = BlockerCode.NONE

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", enum_value(RecommendationRole, self.role, field="role"))
        object.__setattr__(self, "blocker_code", enum_value(BlockerCode, self.blocker_code, field="blocker_code"))
        require_code(self.capability_code, field="capability_code")
        if isinstance(self.score, bool) or not isinstance(self.score, int) or not 0 <= self.score <= 12000:
            raise ContractError("INVALID_RECOMMENDATION_SCORE")

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "Recommendation":
        return cls(**strict_mapping(cls, payload))


@dataclass(frozen=True, slots=True)
class SignerIdentity:
    key_id: str
    fingerprint: str
    signing_version: str
    rotation_generation: int

    def __post_init__(self) -> None:
        require_code(self.key_id, field="key_id")
        require_hash(self.fingerprint, field="fingerprint")
        require_code(self.signing_version, field="signing_version")
        if (
            isinstance(self.rotation_generation, bool)
            or not isinstance(self.rotation_generation, int)
            or self.rotation_generation < 0
        ):
            raise ContractError("INVALID_SIGNER_ROTATION_GENERATION")

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "SignerIdentity":
        return cls(**strict_mapping(cls, payload))


@dataclass(frozen=True, slots=True)
class HeartbeatEnvelope:
    schema_version: str
    envelope_id: str
    trace_id: str
    origin_node_id: str
    signing_node_id: str
    signer_identity: SignerIdentity
    parent_envelope_id: str | None
    root_transaction_id: str
    mission_code: str
    owner_code: str
    matter_code: str
    classification: Classification
    state: NodeState
    capability_hashes: tuple[str, ...]
    blocker_codes: tuple[BlockerCode, ...]
    recommendations: tuple[Recommendation, ...]
    observed_at: str
    expires_at: str
    sequence: int
    hop_count: int
    control_generation: int
    visited_node_ids: tuple[str, ...]
    delegation_ceiling: Authority
    idempotency_key: str
    signature: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError("UNSUPPORTED_SCHEMA_VERSION")
        for field_name in ("envelope_id", "trace_id", "root_transaction_id", "idempotency_key"):
            require_hash(getattr(self, field_name), field=field_name)
        if self.parent_envelope_id is not None:
            require_hash(self.parent_envelope_id, field="parent_envelope_id")
        validate_common_codes(node_id=self.origin_node_id, owner_code=self.owner_code, matter_code=self.matter_code)
        require_code(self.signing_node_id, field="signing_node_id")
        if not isinstance(self.signer_identity, SignerIdentity):
            raise ContractError("SIGNER_IDENTITY_REQUIRED")
        require_code(self.mission_code, field="mission_code")
        object.__setattr__(self, "classification", enum_value(Classification, self.classification, field="classification"))
        object.__setattr__(self, "state", enum_value(NodeState, self.state, field="state"))
        object.__setattr__(self, "delegation_ceiling", enum_value(Authority, self.delegation_ceiling, field="delegation_ceiling"))
        if self.delegation_ceiling is not Authority.A0:
            raise ContractError("HEARTBEAT_AUTHORITY_MUST_BE_A0")
        validate_digest_sequence(self.capability_hashes, field="capability_hashes")
        blocker_codes = tuple(enum_value(BlockerCode, item, field="blocker_codes") for item in self.blocker_codes)
        object.__setattr__(self, "blocker_codes", blocker_codes)
        if len(set(blocker_codes)) != len(blocker_codes):
            raise ContractError("DUPLICATE_BLOCKER_CODE")
        if not isinstance(self.recommendations, tuple) or len(self.recommendations) > 3:
            raise ContractError("TOO_MANY_RECOMMENDATIONS")
        roles = tuple(item.role for item in self.recommendations)
        if len(set(roles)) != len(roles):
            raise ContractError("DUPLICATE_RECOMMENDATION_ROLE")
        observed = parse_utc(self.observed_at, field="observed_at")
        expires = parse_utc(self.expires_at, field="expires_at")
        ttl = int((expires - observed).total_seconds())
        if ttl <= 0 or ttl > MAX_TTL_SECONDS:
            raise ContractError("INVALID_ENVELOPE_TTL")
        for field_name in ("sequence", "hop_count", "control_generation"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ContractError(f"INVALID_NONNEGATIVE_INTEGER:{field_name}")
        if self.signer_identity.rotation_generation != self.control_generation:
            raise ContractError("SIGNER_CONTROL_GENERATION_MISMATCH")
        if self.hop_count > MAX_HOPS:
            raise ContractError("HOP_LIMIT_EXCEEDED")
        if not isinstance(self.visited_node_ids, tuple) or not self.visited_node_ids:
            raise ContractError("VISITED_PATH_REQUIRED")
        if len(self.visited_node_ids) != len(set(self.visited_node_ids)):
            raise ContractError("VISITED_LOOP_DETECTED")
        if self.hop_count != len(self.visited_node_ids) - 1:
            raise ContractError("HOP_PATH_LENGTH_MISMATCH")
        for node_id in self.visited_node_ids:
            require_code(node_id, field="visited_node_ids")
        if self.origin_node_id != self.visited_node_ids[0]:
            raise ContractError("ORIGIN_MUST_START_VISITED_PATH")
        if self.signing_node_id != self.visited_node_ids[-1]:
            raise ContractError("SIGNING_NODE_MUST_END_VISITED_PATH")
        if self.hop_count == 0 and self.parent_envelope_id is not None:
            raise ContractError("ROOT_ENVELOPE_CANNOT_HAVE_PARENT")
        if self.hop_count > 0 and self.parent_envelope_id is None:
            raise ContractError("FORWARDED_ENVELOPE_PARENT_REQUIRED")
        require_hash(self.signature, field="signature", hmac_allowed=True)

    def signing_body(self) -> dict[str, Any]:
        value = canonicalize(self)
        value.pop("signature")
        return value

    def identity_body(self) -> dict[str, Any]:
        value = self.signing_body()
        value.pop("envelope_id")
        value.pop("idempotency_key")
        return value

    def lineage_semantic_body(self) -> dict[str, Any]:
        """Return fields that every forwarding hop must preserve exactly."""
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "origin_node_id": self.origin_node_id,
            "root_transaction_id": self.root_transaction_id,
            "mission_code": self.mission_code,
            "owner_code": self.owner_code,
            "matter_code": self.matter_code,
            "classification": self.classification,
            "state": self.state,
            "capability_hashes": self.capability_hashes,
            "blocker_codes": self.blocker_codes,
            "recommendations": self.recommendations,
            "observed_at": self.observed_at,
            "expires_at": self.expires_at,
            "control_generation": self.control_generation,
            "delegation_ceiling": self.delegation_ceiling,
        }

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "HeartbeatEnvelope":
        values = strict_mapping(cls, payload)
        values["capability_hashes"] = tuple(values["capability_hashes"])
        values["blocker_codes"] = tuple(values["blocker_codes"])
        values["recommendations"] = tuple(
            item if isinstance(item, Recommendation) else Recommendation.from_mapping(item)
            for item in values["recommendations"]
        )
        if not isinstance(values["signer_identity"], SignerIdentity):
            values["signer_identity"] = SignerIdentity.from_mapping(values["signer_identity"])
        values["visited_node_ids"] = tuple(values["visited_node_ids"])
        return cls(**values)


@dataclass(frozen=True, slots=True)
class Receipt:
    receipt_id: str
    envelope_id: str
    accepting_node_id: str
    signer_identity: SignerIdentity
    owner_code: str
    matter_code: str
    accepted_at: str
    control_generation: int
    semantic_hash: str
    signature: str

    def __post_init__(self) -> None:
        for field_name in ("receipt_id", "envelope_id", "semantic_hash"):
            require_hash(getattr(self, field_name), field=field_name)
        validate_common_codes(
            node_id=self.accepting_node_id,
            owner_code=self.owner_code,
            matter_code=self.matter_code,
        )
        if not isinstance(self.signer_identity, SignerIdentity):
            raise ContractError("SIGNER_IDENTITY_REQUIRED")
        parse_utc(self.accepted_at, field="accepted_at")
        if isinstance(self.control_generation, bool) or not isinstance(self.control_generation, int) or self.control_generation < 0:
            raise ContractError("INVALID_CONTROL_GENERATION")
        if self.signer_identity.rotation_generation != self.control_generation:
            raise ContractError("SIGNER_CONTROL_GENERATION_MISMATCH")
        require_hash(self.signature, field="signature", hmac_allowed=True)

    def signing_body(self) -> dict[str, Any]:
        value = canonicalize(self)
        value.pop("signature")
        return value

    def identity_body(self) -> dict[str, Any]:
        value = self.signing_body()
        value.pop("receipt_id")
        return value

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "Receipt":
        values = strict_mapping(cls, payload)
        if not isinstance(values["signer_identity"], SignerIdentity):
            values["signer_identity"] = SignerIdentity.from_mapping(values["signer_identity"])
        return cls(**values)
