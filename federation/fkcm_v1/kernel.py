from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .context import ContextCapsuleCompiler
from .convergence import StateCompiler
from .court import ConvergenceCourt, CourtReceipt
from .models import ContextCapsule, EventEnvelope, RelationFact, SourceLease, StateFact, sha256_obj
from .router import DependencyEdge, DependencyImpactRouter, Subscription


@dataclass(frozen=True, slots=True)
class ShadowResult:
    state_facts: tuple[StateFact, ...]
    relations: tuple[RelationFact, ...]
    capsule: ContextCapsule
    dispatches: tuple[dict, ...]
    court: CourtReceipt
    receipt_sha256: str


class ModisaKdvConvergenceKernel:
    """No-effect convergence layer across Omni Mesh, KDV-GEN2 and BMF shadow history."""

    SCHEMA = "MODISA-FKCM-V1"

    def __init__(self, *, edges: Iterable[DependencyEdge] = (), subscriptions: Iterable[Subscription] = (),
                 max_capsule_chars: int = 24_000) -> None:
        self.state_compiler = StateCompiler()
        self.router = DependencyImpactRouter(edges, subscriptions)
        self.context_compiler = ContextCapsuleCompiler(max_chars=max_capsule_chars)
        self.court = ConvergenceCourt()

    def run_shadow(self, *, events: Iterable[EventEnvelope], compiled_at: str, mission_id: str, objective: str,
                   source_frontier: str, entity_ids: Iterable[str], roots: Iterable[str], capabilities: Iterable[str] = (),
                   blockers: Iterable[str] = (), leases: Iterable[SourceLease] = (), prior_state: Iterable[StateFact] = (),
                   prior_relations: Iterable[RelationFact] = ()) -> ShadowResult:
        events = self.state_compiler.deduplicate_events(events)
        facts, relations = self.state_compiler.compile(events, compiled_at=compiled_at, prior_state=prior_state,
                                                       prior_relations=prior_relations)
        current, stale_holds = self.state_compiler.serve_current(facts, leases)
        dispatch_map = {}
        for event in events:
            for dispatch in self.router.route(event, roots):
                dispatch_map[(dispatch.target, dispatch.topic)] = asdict(dispatch)
        capsule = self.context_compiler.compile(
            mission_id=mission_id,
            objective=objective,
            source_frontier=source_frontier,
            as_of=compiled_at,
            facts=current,
            relations=relations,
            capabilities=capabilities,
            blockers=blockers,
            stale_holds=stale_holds,
            focus_entities=entity_ids,
        )
        court = self.court.evaluate(events=events, facts=facts, relations=relations, entity_ids=entity_ids,
                                    leases=leases, shadow_mode=True, promotion_requested=False)
        body = {
            "schema": self.SCHEMA,
            "event_count": len(events),
            "state_count": len(facts),
            "relation_count": len(relations),
            "dispatch_count": len(dispatch_map),
            "capsule_sha256": capsule.digest,
            "court_state": court.state,
            "court_holds": list(court.holds),
            "court_failures": list(court.failures),
            "provider_effect": False,
            "write_count": 0,
        }
        return ShadowResult(
            state_facts=facts,
            relations=relations,
            capsule=capsule,
            dispatches=tuple(dispatch_map[key] for key in sorted(dispatch_map)),
            court=court,
            receipt_sha256=sha256_obj(body),
        )
