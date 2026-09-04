from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
from typing import Any, Iterable, Mapping

from .convergence import BMF_STATE_MERGE_EVENT_TYPES, StateCompiler
from .models import EventEnvelope, canonical_json, sha256_obj


@dataclass(frozen=True, slots=True)
class BmfProjection:
    stream_id: str
    as_of_recorded_at: str | None
    event_count: int
    current: dict[str, Any]
    directive_ids: tuple[str, ...]
    mission_ids: tuple[str, ...]
    contradictions: tuple[tuple[str, str], ...]
    superseded_event_ids: tuple[str, ...]
    projection_hash: str


@dataclass(frozen=True, slots=True)
class BmfDualRunReceipt:
    state: str
    stream_count: int
    matched_streams: tuple[str, ...]
    mismatches: tuple[str, ...]
    observed_hashes: tuple[tuple[str, str], ...]
    provider_effect: bool
    cutover_authorized: bool
    receipt_sha256: str


def _bmf_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def project_bmf_events(events: Iterable[EventEnvelope], *, as_of_recorded_at: str | None = None) -> tuple[BmfProjection, ...]:
    by_stream: dict[str, list[EventEnvelope]] = {}
    for event in events:
        if not event.schema_version.startswith("BMF-"):
            continue
        stream = str(event.lineage.get("stream_id") or event.source_key).strip()
        if not stream:
            raise ValueError("BMF_STREAM_ID_REQUIRED")
        by_stream.setdefault(stream, []).append(event)

    projections: list[BmfProjection] = []
    for stream_id in sorted(by_stream):
        ordered = sorted(by_stream[stream_id], key=lambda event: (event.event_time, event.source_sequence, event.event_id))
        if as_of_recorded_at is not None:
            ordered = [event for event in ordered if event.event_time <= as_of_recorded_at]
        current: dict[str, Any] = {}
        superseded: set[str] = set()
        contradictions: set[tuple[str, str]] = set()
        directives: set[str] = set()
        missions: set[str] = set()
        for event in ordered:
            superseded.update(event.supersedes)
            for other in event.contradicts:
                contradictions.add(tuple(sorted((event.event_id, other))))
            directive_id = str(event.lineage.get("directive_id") or "").strip()
            mission_id = str(event.lineage.get("mission_id") or "").strip()
            if directive_id:
                directives.add(directive_id)
            if mission_id:
                missions.add(mission_id)
            if event.event_type in BMF_STATE_MERGE_EVENT_TYPES:
                current.update(dict(event.payload))
            elif event.event_type == "STATE_UNSET":
                for key in event.payload.get("keys", ()):
                    current.pop(str(key), None)

        payload = {
            "stream_id": stream_id,
            "as_of_recorded_at": as_of_recorded_at,
            "event_count": len(ordered),
            "current": current,
            "directive_ids": tuple(sorted(directives)),
            "mission_ids": tuple(sorted(missions)),
            "contradictions": tuple(sorted(contradictions)),
            "superseded_event_ids": tuple(sorted(superseded)),
        }
        projections.append(BmfProjection(**payload, projection_hash=_bmf_digest(payload)))
    return tuple(projections)


def compare_bmf_dual_run(
    events: Iterable[EventEnvelope],
    expected: Mapping[str, Mapping[str, Any]],
    *,
    compiled_at: str = "DUAL_RUN",
) -> BmfDualRunReceipt:
    events = tuple(events)
    observed = {projection.stream_id: projection for projection in project_bmf_events(events)}
    facts, _ = StateCompiler(proof_epoch="PE-FKCM-DUALRUN-LOCAL").compile(events, compiled_at=compiled_at)

    entity_by_stream: dict[str, str] = {}
    mapping_conflicts: list[str] = []
    for event in events:
        if not event.schema_version.startswith("BMF-"):
            continue
        stream = str(event.lineage.get("stream_id") or event.source_key).strip()
        prior = entity_by_stream.get(stream)
        if prior and prior != event.entity_id:
            mapping_conflicts.append(f"STREAM_ENTITY_CONFLICT:{stream}")
        entity_by_stream[stream] = event.entity_id

    state_by_entity: dict[str, dict[str, Any]] = {}
    for fact in facts:
        state_by_entity.setdefault(fact.entity_id, {})[fact.field_id] = fact.typed_value

    mismatches: list[str] = list(mapping_conflicts)
    matched: list[str] = []

    if set(observed) != set(expected):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        if missing:
            mismatches.append("MISSING_STREAMS:" + ",".join(missing))
        if extra:
            mismatches.append("EXTRA_STREAMS:" + ",".join(extra))

    for stream_id in sorted(set(observed) & set(expected)):
        actual = observed[stream_id]
        target = expected[stream_id]
        target_current = dict(target.get("current", actual.current))
        entity = entity_by_stream.get(stream_id, "")
        compiled_current = state_by_entity.get(entity, {})
        checks = {
            "event_count": actual.event_count == int(target.get("event_count", actual.event_count)),
            "bmf_oracle_current": actual.current == target_current,
            "gen2_compiled_current": compiled_current == target_current,
            "directive_ids": actual.directive_ids == tuple(sorted(target.get("directive_ids", actual.directive_ids))),
            "mission_ids": actual.mission_ids == tuple(sorted(target.get("mission_ids", actual.mission_ids))),
            "superseded_event_ids": actual.superseded_event_ids == tuple(sorted(target.get("superseded_event_ids", actual.superseded_event_ids))),
            "projection_hash": actual.projection_hash == str(target.get("projection_hash", actual.projection_hash)),
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            mismatches.append(f"{stream_id}:" + ",".join(failed))
        else:
            matched.append(stream_id)

    body = {
        "schema": "MODISA-FKCM-BMF-DUAL-RUN-1",
        "state": "PASS" if not mismatches else "FAIL",
        "stream_count": len(observed),
        "matched_streams": sorted(matched),
        "mismatches": sorted(mismatches),
        "observed_hashes": sorted((stream, projection.projection_hash) for stream, projection in observed.items()),
        "provider_effect": False,
        "cutover_authorized": False,
    }
    return BmfDualRunReceipt(
        state=body["state"],
        stream_count=body["stream_count"],
        matched_streams=tuple(body["matched_streams"]),
        mismatches=tuple(body["mismatches"]),
        observed_hashes=tuple(tuple(item) for item in body["observed_hashes"]),
        provider_effect=False,
        cutover_authorized=False,
        receipt_sha256=sha256_obj(body),
    )
