from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from enum import IntEnum, StrEnum
from typing import Any, Mapping


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_obj(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Authority(IntEnum):
    A0 = 0
    A1 = 1
    A2 = 2
    A3 = 3


class Effect(StrEnum):
    NONE = "NONE"
    READ_ONLY = "READ_ONLY"
    BOUNDED = "BOUNDED_EFFECT"
    CONSEQUENTIAL = "CONSEQUENTIAL_EFFECT"


class TruthClass(StrEnum):
    SOURCE_TRUTH = "SOURCE_TRUTH"
    PROVIDER_READ = "PROVIDER_READ"
    RUNTIME_PROOF = "RUNTIME_PROOF"
    BEHAVIOR_PROOF = "BEHAVIOR_PROOF"
    VALUE_PROOF = "VALUE_PROOF"
    DERIVED_VERIFIED = "DERIVED_VERIFIED"
    EVENT_TRUTH = "EVENT_TRUTH"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"


class Privacy(StrEnum):
    PUBLIC_SAFE = "PUBLIC_SAFE"
    INTERNAL = "P1_INTERNAL"
    PRIVATE = "P2_PRIVATE"
    RESTRICTED = "P3_RESTRICTED"


class ModelError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProofDimensions:
    source: str = "UNASSESSED"
    runtime: str = "UNASSESSED"
    provider: str = "UNASSESSED"
    behavior: str = "UNASSESSED"
    value: str = "UNASSESSED"
    authority: str = "UNASSESSED"
    effect: str = "NONE"

    def claim_ceiling(self) -> str:
        proven = {"PROVEN", "PROVEN_READ", "VERIFIED", "READ_AUTHORITY", "SOURCE_AUTHORITY", "NO_AUTHORITY_EXPANSION"}
        if self.source not in proven:
            return "OBSERVED_ONLY"
        if self.runtime not in proven:
            return "SOURCE_ONLY"
        if self.provider not in proven:
            return "RUNTIME_ONLY"
        if self.behavior not in proven:
            return "PROVIDER_ONLY"
        if self.value not in proven:
            return "BEHAVIOR_ONLY"
        return "VALUE_PROVEN"


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    event_type: str
    entity_id: str
    source_surface: str
    source_key: str
    event_time: str
    observed_time: str
    valid_from: str
    payload: Mapping[str, Any]
    proof_refs: tuple[str, ...] = ()
    authority: Authority = Authority.A1
    effect: Effect = Effect.NONE
    truth_class: TruthClass = TruthClass.EVENT_TRUTH
    privacy: Privacy = Privacy.INTERNAL
    transaction_id: str = ""
    topic: str = "sync.delta.v1"
    source_sequence: int = 0
    lineage: Mapping[str, str] = field(default_factory=dict)
    causal_parent_ids: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    trace_id: str = ""
    span_id: str = ""
    schema_version: str = "FKCM-EVENT-1"

    def __post_init__(self) -> None:
        required = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "source_surface": self.source_surface,
            "source_key": self.source_key,
            "event_time": self.event_time,
            "observed_time": self.observed_time,
            "valid_from": self.valid_from,
            "topic": self.topic,
        }
        for name, value in required.items():
            if not str(value).strip():
                raise ModelError(f"EVENT_REQUIRED:{name}")
        if not isinstance(self.payload, Mapping):
            raise ModelError("EVENT_PAYLOAD_MUST_BE_MAPPING")
        if self.source_sequence < 0:
            raise ModelError("EVENT_SOURCE_SEQUENCE_INVALID")
        if not isinstance(self.lineage, Mapping):
            raise ModelError("EVENT_LINEAGE_MUST_BE_MAPPING")
        if self.effect in {Effect.BOUNDED, Effect.CONSEQUENTIAL} and self.authority < Authority.A2:
            raise ModelError("EFFECT_AUTHORITY_INSUFFICIENT")

    @property
    def payload_hash(self) -> str:
        return sha256_obj(dict(self.payload))

    @property
    def event_hash(self) -> str:
        return sha256_obj(self.canonical_mapping())

    def canonical_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "source_surface": self.source_surface,
            "source_key": self.source_key,
            "event_time": self.event_time,
            "observed_time": self.observed_time,
            "valid_from": self.valid_from,
            "payload": dict(self.payload),
            "proof_refs": sorted(set(self.proof_refs)),
            "authority": self.authority.name,
            "effect": self.effect.value,
            "truth_class": self.truth_class.value,
            "privacy": self.privacy.value,
            "transaction_id": self.transaction_id,
            "topic": self.topic,
            "source_sequence": self.source_sequence,
            "lineage": {str(k): str(v) for k, v in sorted(dict(self.lineage).items()) if str(v).strip()},
            "causal_parent_ids": sorted(set(self.causal_parent_ids)),
            "supersedes": sorted(set(self.supersedes)),
            "contradicts": sorted(set(self.contradicts)),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
        }


@dataclass(frozen=True, slots=True)
class StateFact:
    entity_id: str
    field_id: str
    typed_value: Any
    value_type: str
    source_event_id: str
    authority_source: str
    proof: ProofDimensions
    fresh_until: str
    proof_epoch: str
    compiled_at: str
    superseded_by: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.entity_id, self.field_id)

    @property
    def claim_ceiling(self) -> str:
        return self.proof.claim_ceiling()


@dataclass(frozen=True, slots=True)
class RelationFact:
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    source_event_id: str
    authority_source: str
    truth_class: TruthClass
    privacy: Privacy
    valid_from: str
    compiled_at: str
    superseded_by: str = ""

    @property
    def digest(self) -> str:
        return sha256_obj(asdict(self))


@dataclass(frozen=True, slots=True)
class SourceLease:
    entity_id: str
    field_id: str
    expected_value: str
    observed_at: str
    source_surface: str
    proof_ref: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.entity_id, self.field_id)


@dataclass(frozen=True, slots=True)
class ContextCapsule:
    capsule_id: str
    mission_id: str
    objective: str
    source_frontier: str
    as_of: str
    facts: tuple[dict[str, Any], ...]
    relations: tuple[dict[str, Any], ...]
    capabilities: tuple[str, ...]
    blockers: tuple[str, ...]
    proof_refs: tuple[str, ...]
    stale_holds: tuple[str, ...]
    completeness: str
    char_count: int

    @property
    def digest(self) -> str:
        return sha256_obj(asdict(self))


@dataclass(frozen=True, slots=True)
class DispatchCandidate:
    target: str
    topic: str
    reason: str
    authority_ceiling: str
    effect: str = "NONE"


@dataclass(frozen=True, slots=True)
class WritePlan:
    target: str
    expected_revision: str
    updates: tuple[tuple[str, Any], ...]
    readback_required: bool = True
    mode: str = "SHADOW_READ_ONLY"

    def validate(self) -> None:
        if not self.target:
            raise ModelError("WRITE_PLAN_TARGET_REQUIRED")
        if not self.expected_revision:
            raise ModelError("WRITE_PLAN_COMPARE_AND_SET_REQUIRED")
        if self.mode == "SHADOW_READ_ONLY" and self.updates:
            raise ModelError("SHADOW_WRITE_PLAN_MUST_NOT_MUTATE")
