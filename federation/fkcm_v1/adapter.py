from __future__ import annotations

from typing import Any, Mapping

from .identity import preserve_or_map_entity
from .models import Authority, Effect, EventEnvelope, Privacy, TruthClass, canonical_json


def _authority(value: str | None) -> Authority:
    clean = str(value or "A1").strip().upper()
    if clean in Authority.__members__:
        return Authority[clean]
    aliases = {"SOURCE_TRUTH": Authority.A1, "PROVIDER_READ": Authority.A1, "SOURCE_ADMISSION": Authority.A1}
    return aliases.get(clean, Authority.A1)


def _effect(value: str | None) -> Effect:
    clean = str(value or "NONE").strip().upper()
    aliases = {
        "NONE": Effect.NONE,
        "NO_EFFECT": Effect.NONE,
        "READ_ONLY": Effect.READ_ONLY,
        "NONE_SOURCE_CHANGE": Effect.NONE,
        "BOUNDED": Effect.BOUNDED,
        "BOUNDED_EFFECT": Effect.BOUNDED,
        "CONSEQUENTIAL": Effect.CONSEQUENTIAL,
        "CONSEQUENTIAL_EFFECT": Effect.CONSEQUENTIAL,
    }
    return aliases.get(clean, Effect.NONE)


def from_gen2_row(row: Mapping[str, Any]) -> EventEnvelope:
    proof_ref = str(row.get("Proof_Ref", "")).strip()
    payload = row.get("Payload")
    if not isinstance(payload, Mapping):
        payload = {
            "payload_hash": row.get("Payload_Hash", ""),
            "notes": row.get("Notes", ""),
        }
    return EventEnvelope(
        event_id=str(row["Event_ID"]),
        event_type=str(row["Event_Type"]),
        entity_id=str(row["Entity_ID"]),
        source_surface=str(row["Source_Surface"]),
        source_key=str(row["Source_Key"]),
        event_time=str(row["Event_Time"]),
        observed_time=str(row.get("Observed_Time") or row["Event_Time"]),
        valid_from=str(row.get("Valid_From") or row["Event_Time"]),
        payload=payload,
        proof_refs=(proof_ref,) if proof_ref else (),
        authority=_authority(row.get("Authority_Class")),
        effect=_effect(row.get("Effect_Class")),
        transaction_id=str(row.get("Transaction_ID", "")),
        topic=str(row.get("Topic", "sync.delta.v1")),
    )


def from_bmf_row(row: Mapping[str, Any]) -> EventEnvelope:
    import json

    def parse_json_field(name: str, default: Any) -> Any:
        raw = row.get(name, default)
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(str(raw or canonical_json(default)))
        except json.JSONDecodeError:
            return default

    payload = parse_json_field("payload_json", {})
    refs = tuple(str(x) for x in parse_json_field("source_refs_json", []))
    proof_refs = tuple(str(x) for x in parse_json_field("proof_refs_json", [])) + refs
    stream = str(row["stream_id"]).strip()
    mission = str(row.get("mission_id", "")).strip()
    workstream = str(row.get("workstream_id", "")).strip()
    directive = str(row.get("directive_id", "")).strip()
    entity = preserve_or_map_entity(None, "bmf-stream", stream, "federation")
    lineage = {
        key: value
        for key, value in {
            "stream_id": stream,
            "directive_id": directive,
            "mission_id": mission,
            "workstream_id": workstream,
        }.items()
        if value
    }
    try:
        source_sequence = int(float(str(row.get("stream_version") or "0")))
    except ValueError as exc:
        raise ValueError("BMF_STREAM_VERSION_INVALID") from exc
    return EventEnvelope(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        entity_id=entity,
        source_surface="KDV_BMF_SHADOW",
        source_key=stream,
        event_time=str(row["recorded_at"]),
        observed_time=str(row.get("provider_persisted_at_sast") or row["recorded_at"]),
        valid_from=str(row.get("valid_at") or row["recorded_at"]),
        payload=payload,
        proof_refs=proof_refs,
        authority=Authority.A1,
        effect=Effect.NONE,
        truth_class=TruthClass(str(row.get("truth_class") or "EVENT_TRUTH")),
        privacy=Privacy(str(row.get("privacy_class") or "P1_INTERNAL")),
        transaction_id=str(row.get("idempotency_key", "")),
        topic="sync.delta.v1",
        source_sequence=source_sequence,
        lineage=lineage,
        causal_parent_ids=tuple(str(x) for x in parse_json_field("causal_parent_ids_json", [])),
        supersedes=tuple(str(x) for x in parse_json_field("supersedes_json", [])),
        contradicts=tuple(str(x) for x in parse_json_field("contradicts_json", [])),
        schema_version=f"BMF-{row.get('schema_version', '1')}",
    )


def from_cloudevent(event: Mapping[str, Any], *, topic: str, authority: Authority = Authority.A1,
                    effect: Effect = Effect.NONE, privacy: Privacy = Privacy.INTERNAL) -> EventEnvelope:
    data = event.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("CloudEvent data must be a mapping")
    entity = str(data.get("entity_id") or "").strip()
    if not entity:
        entity = preserve_or_map_entity(None, "event-source", str(event.get("source", "unknown")), "federation")
    time = str(event.get("time") or data.get("observed_at") or "")
    return EventEnvelope(
        event_id=str(event["id"]),
        event_type=str(event["type"]),
        entity_id=entity,
        source_surface=str(event.get("source", "CLOUDEVENT")),
        source_key=str(data.get("source_key") or event.get("source", "")),
        event_time=time,
        observed_time=time,
        valid_from=str(data.get("valid_from") or time),
        payload=dict(data),
        proof_refs=tuple(str(x) for x in data.get("proof_refs", ())),
        authority=authority,
        effect=effect,
        truth_class=TruthClass(str(data.get("truth_class", "EVENT_TRUTH"))),
        privacy=privacy,
        transaction_id=str(data.get("idempotency_key", "")),
        topic=topic,
        trace_id=str(data.get("trace_id", "")),
        span_id=str(data.get("span_id", "")),
    )


def to_gen2_event_row(event: EventEnvelope) -> dict[str, Any]:
    return {
        "Event_ID": event.event_id,
        "Event_Type": event.event_type,
        "Entity_ID": event.entity_id,
        "Source_Surface": event.source_surface,
        "Source_Key": event.source_key,
        "Event_Time": event.event_time,
        "Observed_Time": event.observed_time,
        "Recorded_Time": event.observed_time,
        "Valid_From": event.valid_from,
        "Superseded_At": "",
        "Payload_Hash": event.payload_hash,
        "Proof_Ref": ";".join(event.proof_refs),
        "Authority_Class": event.authority.name,
        "Effect_Class": event.effect.value,
        "Transaction_ID": event.transaction_id,
        "Notes": f"FKCM normalized; event_hash={event.event_hash}; topic={event.topic}",
    }
