from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .models import ContextCapsule, RelationFact, StateFact, canonical_json, sha256_obj


class ContextCapsuleCompiler:
    def __init__(self, max_chars: int = 24_000, max_facts: int = 64, max_relations: int = 64) -> None:
        if min(max_chars, max_facts, max_relations) <= 0:
            raise ValueError("context budgets must be positive")
        self.max_chars = max_chars
        self.max_facts = max_facts
        self.max_relations = max_relations

    def compile(self, *, mission_id: str, objective: str, source_frontier: str, as_of: str,
                facts: Iterable[StateFact], relations: Iterable[RelationFact], capabilities: Iterable[str] = (),
                blockers: Iterable[str] = (), stale_holds: Iterable[str] = (), focus_entities: Iterable[str] = ()) -> ContextCapsule:
        focus = set(focus_entities)
        fact_rows = []
        proof_refs: set[str] = set()
        for fact in facts:
            score = 10 if fact.entity_id in focus else 1
            if fact.field_id in {"current_sha", "connection_state", "mission_state", "next_action"}:
                score += 5
            row = {
                "entity_id": fact.entity_id,
                "field_id": fact.field_id,
                "value": fact.typed_value,
                "claim_ceiling": fact.claim_ceiling,
                "authority_source": fact.authority_source,
                "source_event_id": fact.source_event_id,
                "fresh_until": fact.fresh_until,
                "proof_epoch": fact.proof_epoch,
                "score": score,
            }
            fact_rows.append(row)
            proof_refs.add(fact.source_event_id)
        fact_rows.sort(key=lambda r: (-int(r["score"]), r["entity_id"], r["field_id"]))
        fact_rows = fact_rows[: self.max_facts]

        relation_rows = []
        for rel in relations:
            score = 10 if rel.subject_entity_id in focus or rel.object_entity_id in focus else 1
            row = {
                "relation_id": rel.relation_id,
                "subject": rel.subject_entity_id,
                "predicate": rel.predicate,
                "object": rel.object_entity_id,
                "truth_class": rel.truth_class.value,
                "source_event_id": rel.source_event_id,
                "score": score,
            }
            relation_rows.append(row)
            proof_refs.add(rel.source_event_id)
        relation_rows.sort(key=lambda r: (-int(r["score"]), r["relation_id"]))
        relation_rows = relation_rows[: self.max_relations]

        base = {
            "mission_id": mission_id,
            "objective": objective,
            "source_frontier": source_frontier,
            "as_of": as_of,
            "facts": fact_rows,
            "relations": relation_rows,
            "capabilities": sorted(set(capabilities)),
            "blockers": sorted(set(blockers)),
            "proof_refs": sorted(proof_refs),
            "stale_holds": sorted(set(stale_holds)),
        }
        while len(canonical_json(base)) > self.max_chars and (base["facts"] or base["relations"]):
            if base["relations"] and (not base["facts"] or base["relations"][-1]["score"] <= base["facts"][-1]["score"]):
                base["relations"].pop()
            elif base["facts"]:
                base["facts"].pop()
        if len(canonical_json(base)) > self.max_chars:
            raise ValueError("CONTEXT_CAPSULE_BUDGET_UNSATISFIABLE")
        completeness = "CURRENT_WITH_HOLDS" if base["stale_holds"] else "CURRENT_BOUNDED"
        capsule_id = "CAPSULE-FKCM-" + sha256_obj(base).split(":", 1)[1][:20].upper()
        return ContextCapsule(
            capsule_id=capsule_id,
            mission_id=mission_id,
            objective=objective,
            source_frontier=source_frontier,
            as_of=as_of,
            facts=tuple({k: v for k, v in row.items() if k != "score"} for row in base["facts"]),
            relations=tuple({k: v for k, v in row.items() if k != "score"} for row in base["relations"]),
            capabilities=tuple(base["capabilities"]),
            blockers=tuple(base["blockers"]),
            proof_refs=tuple(base["proof_refs"]),
            stale_holds=tuple(base["stale_holds"]),
            completeness=completeness,
            char_count=len(canonical_json(base)),
        )
