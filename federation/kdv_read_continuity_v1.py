"""Provider-neutral read continuity for Kim Dataverse.

This module creates and restores a deterministic, non-authoritative local snapshot
from caller-supplied KDV/FKCM events. It reuses FKCM deterministic convergence,
KDV currentness contracts, and SOVARA sovereign backup. It contains no provider
credentials and exposes no write path.

A restored snapshot can answer only AS_OF reads. A present-tense "current now"
request always requires a fresh provider/canonical read.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from evidenceops.kim_dataverse.projection_contract import (
    CompiledProjection,
    ProjectionContractError,
    SourceFrontierObservation,
    compile_projection,
)
from federation.fkcm_v1.convergence import StateCompiler
from federation.fkcm_v1.models import (
    Authority,
    Effect,
    EventEnvelope,
    Privacy,
    RelationFact,
    StateFact,
    TruthClass,
)
from federation_consolidation.sovara_sovereign_backup import (
    ArtifactClass,
    ArtifactInput,
    BackupEventType,
    BackupError,
    build_backup_plan,
    restore_snapshot_chain,
    verify_archive,
)

SCHEMA = "FUSE-KDV-READ-CONTINUITY-V1"
VERSION = "1.0.0"
METADATA_NAME = "KDV_CONTINUITY_METADATA.json"
EVENTS_NAME = "KDV_CONTINUITY_EVENTS.jsonl"
MIRROR_ROLE = "NONAUTHORITATIVE_READ_CONTINUITY"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    return value


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha(value: bytes) -> str:
    return sha256(value).hexdigest()


def _hex64(value: str, code: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise ValueError(code)
    return text


def _required(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(code)
    return text


def _event_from_mapping(raw: Mapping[str, Any]) -> EventEnvelope:
    return EventEnvelope(
        event_id=_required(raw.get("event_id"), "KDV_CONTINUITY_EVENT_ID_REQUIRED"),
        event_type=_required(raw.get("event_type"), "KDV_CONTINUITY_EVENT_TYPE_REQUIRED"),
        entity_id=_required(raw.get("entity_id"), "KDV_CONTINUITY_ENTITY_REQUIRED"),
        source_surface=_required(raw.get("source_surface"), "KDV_CONTINUITY_SOURCE_SURFACE_REQUIRED"),
        source_key=_required(raw.get("source_key"), "KDV_CONTINUITY_SOURCE_KEY_REQUIRED"),
        event_time=_required(raw.get("event_time"), "KDV_CONTINUITY_EVENT_TIME_REQUIRED"),
        observed_time=_required(raw.get("observed_time"), "KDV_CONTINUITY_OBSERVED_TIME_REQUIRED"),
        valid_from=_required(raw.get("valid_from"), "KDV_CONTINUITY_VALID_FROM_REQUIRED"),
        payload=dict(raw.get("payload") or {}),
        proof_refs=tuple(str(v) for v in raw.get("proof_refs") or ()),
        authority=Authority[str(raw.get("authority") or "A1")],
        effect=Effect(str(raw.get("effect") or "NONE")),
        truth_class=TruthClass(str(raw.get("truth_class") or "EVENT_TRUTH")),
        privacy=Privacy(str(raw.get("privacy") or "P1_INTERNAL")),
        transaction_id=str(raw.get("transaction_id") or ""),
        topic=str(raw.get("topic") or "sync.delta.v1"),
        source_sequence=int(raw.get("source_sequence") or 0),
        lineage={str(k): str(v) for k, v in dict(raw.get("lineage") or {}).items()},
        causal_parent_ids=tuple(str(v) for v in raw.get("causal_parent_ids") or ()),
        supersedes=tuple(str(v) for v in raw.get("supersedes") or ()),
        contradicts=tuple(str(v) for v in raw.get("contradicts") or ()),
        trace_id=str(raw.get("trace_id") or ""),
        span_id=str(raw.get("span_id") or ""),
        schema_version=str(raw.get("schema") or "FKCM-EVENT-1"),
    )


def _projection_payload(
    facts: Iterable[StateFact],
    relations: Iterable[RelationFact],
) -> dict[str, Any]:
    return {
        "facts": [_jsonable(item) for item in sorted(facts, key=lambda item: item.key)],
        "relations": [
            _jsonable(item)
            for item in sorted(relations, key=lambda item: item.relation_id)
        ],
    }


@dataclass(frozen=True, slots=True)
class ContinuitySnapshot:
    schema: str
    version: str
    source_id: str
    source_revision: str
    observed_at: str
    provider_read_verified_at_capture: bool
    schema_sha256: str
    event_count: int
    events_sha256: str
    projection_sha256: str
    archive_sha256: str
    manifest_sha256: str
    archive_bytes: bytes
    mirror_role: str
    canonical_authority: bool
    provider_effect_authorized: bool


@dataclass(frozen=True, slots=True)
class AsOfReadReceipt:
    entity_id: str
    field_id: str
    found: bool
    value: Any
    value_type: str
    source_event_id: str
    source_revision: str
    observed_at: str
    as_of_only: bool
    present_tense_current_claim_allowed: bool
    canonical_authority: bool
    provider_effect_authorized: bool


@dataclass(frozen=True, slots=True)
class ContinuityRestoreReceipt:
    source_id: str
    source_revision: str
    observed_at: str
    schema_sha256: str
    event_count: int
    events_sha256: str
    projection_sha256: str
    projection_replay_equal: bool
    archive_sha256: str
    archive_sha256_verified: bool
    provider_read_verified_at_capture: bool
    as_of_only: bool
    present_tense_current_claim_allowed: bool
    canonical_authority: bool
    provider_effect_authorized: bool
    receipt_sha256: str


class KDVContinuityReader:
    def __init__(
        self,
        *,
        metadata: Mapping[str, Any],
        events: tuple[EventEnvelope, ...],
        facts: tuple[StateFact, ...],
        relations: tuple[RelationFact, ...],
        restore_receipt: ContinuityRestoreReceipt,
    ) -> None:
        self.metadata = dict(metadata)
        self.events = events
        self.facts = facts
        self.relations = relations
        self.restore_receipt = restore_receipt
        self._facts = {fact.key: fact for fact in facts}

    def currentness(self) -> CompiledProjection:
        source = SourceFrontierObservation(
            source_id=self.restore_receipt.source_id,
            version_or_sha=self.restore_receipt.source_revision,
            observed_at=self.restore_receipt.observed_at,
            verification_state=(
                "PROVIDER_READ_VERIFIED_AT_CAPTURE"
                if self.restore_receipt.provider_read_verified_at_capture
                else "CALLER_SUPPLIED_CAPTURE"
            ),
            query_time_provider_read=False,
        )
        return compile_projection(source=source)

    def query(
        self,
        entity_id: str,
        field_id: str,
        *,
        require_current: bool = False,
    ) -> AsOfReadReceipt:
        if require_current:
            raise ProjectionContractError("KDV_PROVIDER_READ_REQUIRED_FOR_PRESENT_TENSE")
        key = (
            _required(entity_id, "KDV_CONTINUITY_QUERY_ENTITY_REQUIRED"),
            _required(field_id, "KDV_CONTINUITY_QUERY_FIELD_REQUIRED"),
        )
        fact = self._facts.get(key)
        return AsOfReadReceipt(
            entity_id=key[0],
            field_id=key[1],
            found=fact is not None,
            value=None if fact is None else fact.typed_value,
            value_type="" if fact is None else fact.value_type,
            source_event_id="" if fact is None else fact.source_event_id,
            source_revision=self.restore_receipt.source_revision,
            observed_at=self.restore_receipt.observed_at,
            as_of_only=True,
            present_tense_current_claim_allowed=False,
            canonical_authority=False,
            provider_effect_authorized=False,
        )


def build_continuity_snapshot(
    events: Iterable[EventEnvelope],
    *,
    source_id: str,
    source_revision: str,
    observed_at: str,
    schema_sha256: str,
    provider_read_verified_at_capture: bool,
) -> ContinuitySnapshot:
    source_id = _required(source_id, "KDV_CONTINUITY_SOURCE_ID_REQUIRED")
    source_revision = _required(source_revision, "KDV_CONTINUITY_SOURCE_REVISION_REQUIRED")
    observed_at = _required(observed_at, "KDV_CONTINUITY_OBSERVED_AT_REQUIRED")
    schema_sha256 = _hex64(schema_sha256, "KDV_CONTINUITY_SCHEMA_SHA256_INVALID")
    if provider_read_verified_at_capture is not True and provider_read_verified_at_capture is not False:
        raise ValueError("KDV_CONTINUITY_PROVIDER_READ_BOOLEAN_REQUIRED")

    compiler = StateCompiler(proof_epoch="PE-KDV-READ-CONTINUITY-V1")
    ordered = compiler.deduplicate_events(tuple(events))
    if not ordered:
        raise ValueError("KDV_CONTINUITY_EVENTS_REQUIRED")
    facts, relations = compiler.compile(ordered, compiled_at=observed_at)

    event_bytes = b"".join(_canonical(event.canonical_mapping()) for event in ordered)
    projection_payload = _projection_payload(facts, relations)
    projection_sha256 = _sha(_canonical(projection_payload))
    events_sha256 = _sha(event_bytes)

    metadata = {
        "schema": SCHEMA,
        "version": VERSION,
        "mirror_role": MIRROR_ROLE,
        "source_id": source_id,
        "source_revision": source_revision,
        "observed_at": observed_at,
        "provider_read_verified_at_capture": bool(provider_read_verified_at_capture),
        "schema_sha256": schema_sha256,
        "event_count": len(ordered),
        "events_sha256": events_sha256,
        "projection_sha256": projection_sha256,
        "as_of_only": True,
        "present_tense_current_claim_allowed": False,
        "canonical_authority": False,
        "provider_effect_authorized": False,
        "write_authority": False,
    }
    metadata_bytes = _canonical(metadata)
    event_id = "kdv-read-continuity-" + _sha(metadata_bytes + event_bytes)[:24]
    plan = build_backup_plan(
        event_type=BackupEventType.MANUAL_CHECKPOINT,
        event_id=event_id,
        created_at=observed_at,
        source_identity="KDV_NONAUTHORITATIVE_READ_CONTINUITY",
        source_version=source_revision,
        artifacts=(
            ArtifactInput(
                logical_name=METADATA_NAME,
                content=metadata_bytes,
                media_type="application/json",
                classification=ArtifactClass.PRIVATE_CONTROL,
                source_ref=f"{source_id}:{source_revision}",
                email_eligible=False,
            ),
            ArtifactInput(
                logical_name=EVENTS_NAME,
                content=event_bytes,
                media_type="application/x-ndjson",
                classification=ArtifactClass.PRIVATE_CONTROL,
                source_ref=f"{source_id}:{source_revision}",
                email_eligible=False,
            ),
        ),
        force_full=True,
    )
    if plan.archive_bytes is None or plan.archive_sha256 is None:
        raise RuntimeError("KDV_CONTINUITY_ARCHIVE_MISSING")
    verify_archive(plan)
    return ContinuitySnapshot(
        schema=SCHEMA,
        version=VERSION,
        source_id=source_id,
        source_revision=source_revision,
        observed_at=observed_at,
        provider_read_verified_at_capture=bool(provider_read_verified_at_capture),
        schema_sha256=schema_sha256,
        event_count=len(ordered),
        events_sha256=events_sha256,
        projection_sha256=projection_sha256,
        archive_sha256=plan.archive_sha256,
        manifest_sha256=plan.manifest_sha256,
        archive_bytes=plan.archive_bytes,
        mirror_role=MIRROR_ROLE,
        canonical_authority=False,
        provider_effect_authorized=False,
    )


def restore_continuity_snapshot(
    archive_bytes: bytes,
    *,
    expected_archive_sha256: str | None = None,
) -> KDVContinuityReader:
    observed_archive_sha = _sha(bytes(archive_bytes))
    if expected_archive_sha256 is not None:
        expected = _hex64(
            expected_archive_sha256,
            "KDV_CONTINUITY_EXPECTED_ARCHIVE_SHA_INVALID",
        )
        if observed_archive_sha != expected:
            raise BackupError("KDV_CONTINUITY_ARCHIVE_SHA256_MISMATCH")

    restored = restore_snapshot_chain((bytes(archive_bytes),))
    if set(restored) != {METADATA_NAME, EVENTS_NAME}:
        raise BackupError("KDV_CONTINUITY_ARTIFACT_SET_INVALID")
    metadata = json.loads(restored[METADATA_NAME].decode("utf-8"))
    if metadata.get("schema") != SCHEMA or metadata.get("mirror_role") != MIRROR_ROLE:
        raise BackupError("KDV_CONTINUITY_METADATA_INVALID")
    if metadata.get("canonical_authority") is not False:
        raise BackupError("KDV_CONTINUITY_CANONICAL_AUTHORITY_FORBIDDEN")
    if metadata.get("present_tense_current_claim_allowed") is not False:
        raise BackupError("KDV_CONTINUITY_PRESENT_TENSE_FORBIDDEN")
    if metadata.get("provider_effect_authorized") is not False or metadata.get("write_authority") is not False:
        raise BackupError("KDV_CONTINUITY_EFFECT_OR_WRITE_AUTHORITY_FORBIDDEN")

    events_bytes = restored[EVENTS_NAME]
    if _sha(events_bytes) != str(metadata.get("events_sha256") or ""):
        raise BackupError("KDV_CONTINUITY_EVENTS_SHA256_MISMATCH")
    rows = [line for line in events_bytes.splitlines() if line]
    if len(rows) != int(metadata.get("event_count") or -1):
        raise BackupError("KDV_CONTINUITY_EVENT_COUNT_MISMATCH")
    events = tuple(_event_from_mapping(json.loads(line.decode("utf-8"))) for line in rows)

    compiler = StateCompiler(proof_epoch="PE-KDV-READ-CONTINUITY-V1")
    facts, relations = compiler.compile(events, compiled_at=str(metadata["observed_at"]))
    replay_hash = _sha(_canonical(_projection_payload(facts, relations)))
    projection_equal = replay_hash == str(metadata.get("projection_sha256") or "")
    if not projection_equal:
        raise BackupError("KDV_CONTINUITY_PROJECTION_REPLAY_MISMATCH")

    source = SourceFrontierObservation(
        source_id=str(metadata["source_id"]),
        version_or_sha=str(metadata["source_revision"]),
        observed_at=str(metadata["observed_at"]),
        verification_state=(
            "PROVIDER_READ_VERIFIED_AT_CAPTURE"
            if metadata.get("provider_read_verified_at_capture") is True
            else "CALLER_SUPPLIED_CAPTURE"
        ),
        query_time_provider_read=False,
    )
    currentness = compile_projection(source=source)
    payload = {
        "source_id": source.source_id,
        "source_revision": source.version_or_sha,
        "observed_at": source.observed_at,
        "schema_sha256": str(metadata["schema_sha256"]),
        "event_count": len(events),
        "events_sha256": str(metadata["events_sha256"]),
        "projection_sha256": replay_hash,
        "projection_replay_equal": projection_equal,
        "archive_sha256": observed_archive_sha,
        "archive_sha256_verified": (
            expected_archive_sha256 is None
            or observed_archive_sha == str(expected_archive_sha256).lower()
        ),
        "provider_read_verified_at_capture": bool(
            metadata.get("provider_read_verified_at_capture")
        ),
        "as_of_only": currentness.as_of_only,
        "present_tense_current_claim_allowed": currentness.present_tense_source_claim_allowed,
        "canonical_authority": False,
        "provider_effect_authorized": False,
    }
    receipt = ContinuityRestoreReceipt(
        **payload,
        receipt_sha256=_sha(_canonical(payload)),
    )
    return KDVContinuityReader(
        metadata=metadata,
        events=events,
        facts=facts,
        relations=relations,
        restore_receipt=receipt,
    )


__all__ = [
    "AsOfReadReceipt",
    "ContinuityRestoreReceipt",
    "ContinuitySnapshot",
    "KDVContinuityReader",
    "build_continuity_snapshot",
    "restore_continuity_snapshot",
]
