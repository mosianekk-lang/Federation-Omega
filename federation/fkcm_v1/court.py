from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Effect, EventEnvelope, RelationFact, SourceLease, StateFact


@dataclass(frozen=True, slots=True)
class CourtReceipt:
    state: str
    checks: tuple[str, ...]
    holds: tuple[str, ...]
    failures: tuple[str, ...]
    promotion_eligible: bool


class ConvergenceCourt:
    """Fail-closed release court for shadow convergence and future promotion."""

    def evaluate(self, *, events: Iterable[EventEnvelope], facts: Iterable[StateFact], relations: Iterable[RelationFact],
                 entity_ids: Iterable[str], leases: Iterable[SourceLease] = (), shadow_mode: bool = True,
                 promotion_requested: bool = False) -> CourtReceipt:
        events = tuple(events)
        facts = tuple(facts)
        relations = tuple(relations)
        entity_ids = set(entity_ids)
        leases = {lease.key: lease for lease in leases}
        checks: list[str] = []
        holds: list[str] = []
        failures: list[str] = []

        ids: dict[str, str] = {}
        for event in events:
            prior = ids.get(event.event_id)
            if prior and prior != event.event_hash:
                failures.append(f"EVENT_ID_CONFLICT:{event.event_id}")
            ids[event.event_id] = event.event_hash
            if shadow_mode and event.effect not in {Effect.NONE, Effect.READ_ONLY}:
                failures.append(f"SHADOW_EFFECT_FORBIDDEN:{event.event_id}")
        checks.append("EVENT_IDEMPOTENCY")
        checks.append("SHADOW_EFFECT_BOUNDARY")

        fact_keys = [fact.key for fact in facts]
        if len(fact_keys) != len(set(fact_keys)):
            failures.append("DUPLICATE_CURRENT_STATE_KEY")
        event_ids = set(ids)
        for fact in facts:
            if fact.source_event_id not in event_ids:
                failures.append(f"STATE_SOURCE_EVENT_MISSING:{fact.entity_id}:{fact.field_id}")
            if fact.fresh_until == "LEASE_RENEW_ON_QUERY":
                lease = leases.get(fact.key)
                if not lease or str(lease.expected_value) != str(fact.typed_value):
                    holds.append(f"FRESH_SOURCE_LEASE_REQUIRED:{fact.entity_id}:{fact.field_id}")
            if promotion_requested and ("UNPINNED" in fact.proof_epoch or "BOOTSTRAP" in fact.proof_epoch):
                holds.append(f"PINNED_PROOF_EPOCH_REQUIRED:{fact.entity_id}:{fact.field_id}")
        checks.extend(("CURRENT_STATE_UNIQUENESS", "STATE_PROVENANCE", "SOURCE_FRESHNESS"))

        for rel in relations:
            if rel.source_event_id not in event_ids:
                failures.append(f"RELATION_SOURCE_EVENT_MISSING:{rel.relation_id}")
            if rel.subject_entity_id not in entity_ids or rel.object_entity_id not in entity_ids:
                failures.append(f"DANGLING_RELATION:{rel.relation_id}")
        checks.append("RELATION_REFERENTIAL_INTEGRITY")

        if failures:
            state = "FAIL"
        elif holds:
            state = "PASS_WITH_HOLDS"
        else:
            state = "PASS"
        return CourtReceipt(
            state=state,
            checks=tuple(checks),
            holds=tuple(sorted(set(holds))),
            failures=tuple(sorted(set(failures))),
            promotion_eligible=state == "PASS" and promotion_requested,
        )
