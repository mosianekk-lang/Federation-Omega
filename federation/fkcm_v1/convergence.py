from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping, Any

from .models import EventEnvelope, ProofDimensions, RelationFact, SourceLease, StateFact, TruthClass, Privacy


class ConvergenceError(ValueError):
    pass


BMF_STATE_MERGE_EVENT_TYPES = frozenset({
    "STATE_SET", "DECISION_ACCEPTED", "RESULT_VERIFIED", "BLOCKER_SET", "NEXT_ACTION_SET"
})


def _event_order(event: EventEnvelope) -> tuple[object, ...]:
    if event.schema_version.startswith("BMF-"):
        return (event.event_time, event.source_sequence, event.event_id)
    return (event.valid_from, event.observed_time, event.source_sequence, event.event_id)


def _proof_from_payload(payload: Mapping[str, Any]) -> ProofDimensions:
    raw = payload.get("proof_dimensions", {})
    if not isinstance(raw, Mapping):
        raw = {}
    return ProofDimensions(
        source=str(raw.get("source", "PROVEN" if payload.get("source_proven") else "UNASSESSED")),
        runtime=str(raw.get("runtime", "UNASSESSED")),
        provider=str(raw.get("provider", "UNASSESSED")),
        behavior=str(raw.get("behavior", "UNASSESSED")),
        value=str(raw.get("value", "UNASSESSED")),
        authority=str(raw.get("authority", "READ_AUTHORITY")),
        effect=str(raw.get("effect", "NONE")),
    )


class StateCompiler:
    """Deterministic event-first compiler for KDV-GEN2 CURRENT_STATE and relations."""

    def __init__(self, proof_epoch: str = "PE-FKCM-SHADOW-1") -> None:
        self.proof_epoch = proof_epoch

    def deduplicate_events(self, events: Iterable[EventEnvelope]) -> tuple[EventEnvelope, ...]:
        by_id: dict[str, EventEnvelope] = {}
        by_txn: dict[str, str] = {}
        for event in events:
            prior = by_id.get(event.event_id)
            if prior is not None:
                if prior.event_hash != event.event_hash:
                    raise ConvergenceError(f"EVENT_ID_CONFLICT:{event.event_id}")
                continue
            if event.transaction_id:
                prior_hash = by_txn.get(event.transaction_id)
                if prior_hash and prior_hash != event.event_hash:
                    raise ConvergenceError(f"IDEMPOTENCY_CONFLICT:{event.transaction_id}")
                by_txn[event.transaction_id] = event.event_hash
            by_id[event.event_id] = event
        return tuple(sorted(by_id.values(), key=_event_order))

    def compile(self, events: Iterable[EventEnvelope], *, compiled_at: str,
                prior_state: Iterable[StateFact] = (), prior_relations: Iterable[RelationFact] = ()) -> tuple[tuple[StateFact, ...], tuple[RelationFact, ...]]:
        state: dict[tuple[str, str], StateFact] = {fact.key: fact for fact in prior_state if not fact.superseded_by}
        relations: dict[str, RelationFact] = {rel.relation_id: rel for rel in prior_relations if not rel.superseded_by}
        for event in self.deduplicate_events(events):
            payload = dict(event.payload)
            if event.event_type.endswith("STATE_UNSET") or event.event_type == "STATE_UNSET":
                for field in payload.get("keys", ()):
                    state.pop((event.entity_id, str(field)), None)
                continue

            fields = payload.get("fields")
            if not isinstance(fields, Mapping):
                fields = {}
                if event.schema_version.startswith("BMF-") and event.event_type in BMF_STATE_MERGE_EVENT_TYPES:
                    fields = payload
                elif "field_id" in payload and "value" in payload:
                    fields[str(payload["field_id"])] = payload["value"]
                elif event.event_type in {"SOURCE_FRONTIER_OBSERVED", "SOURCE_ADMISSION_PROMOTED"} and "current_sha" in payload:
                    fields["current_sha"] = payload["current_sha"]
            proof = _proof_from_payload(payload)
            fresh_until = str(payload.get("fresh_until", "LEASE_RENEW_ON_QUERY"))
            for field_id, value in fields.items():
                key = (event.entity_id, str(field_id))
                state[key] = StateFact(
                    entity_id=event.entity_id,
                    field_id=str(field_id),
                    typed_value=value,
                    value_type=type(value).__name__,
                    source_event_id=event.event_id,
                    authority_source=event.source_surface,
                    proof=proof,
                    fresh_until=fresh_until,
                    proof_epoch=str(payload.get("proof_epoch", self.proof_epoch)),
                    compiled_at=compiled_at,
                )

            if event.event_type in {"RELATION_ASSERTED", "com.federation.relation.asserted"}:
                subject = str(payload.get("subject_entity_id") or event.entity_id)
                predicate = str(payload.get("predicate") or "")
                obj = str(payload.get("object_entity_id") or "")
                if not predicate or not obj:
                    raise ConvergenceError("RELATION_FIELDS_REQUIRED")
                rel_id = str(payload.get("relation_id") or f"REL::{subject}::{predicate}::{obj}")
                relations[rel_id] = RelationFact(
                    relation_id=rel_id,
                    subject_entity_id=subject,
                    predicate=predicate,
                    object_entity_id=obj,
                    source_event_id=event.event_id,
                    authority_source=event.source_surface,
                    truth_class=event.truth_class,
                    privacy=event.privacy,
                    valid_from=event.valid_from,
                    compiled_at=compiled_at,
                )
            if event.event_type in {"RELATION_RETRACTED", "com.federation.relation.retracted"}:
                rel_id = str(payload.get("relation_id") or "")
                relations.pop(rel_id, None)
        return tuple(sorted(state.values(), key=lambda f: f.key)), tuple(sorted(relations.values(), key=lambda r: r.relation_id))

    @staticmethod
    def serve_current(facts: Iterable[StateFact], leases: Iterable[SourceLease] = ()) -> tuple[tuple[StateFact, ...], tuple[str, ...]]:
        lease_map = {lease.key: lease for lease in leases}
        served: list[StateFact] = []
        holds: list[str] = []
        for fact in facts:
            if fact.fresh_until == "LEASE_RENEW_ON_QUERY":
                lease = lease_map.get(fact.key)
                if lease is None or str(lease.expected_value) != str(fact.typed_value):
                    holds.append(f"STALE_LEASE_REQUIRED:{fact.entity_id}:{fact.field_id}")
                    continue
            served.append(fact)
        return tuple(served), tuple(sorted(holds))
