from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import DispatchCandidate, EventEnvelope


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    edge_id: str
    from_node: str
    relation: str
    to_node: str
    state: str = "ACTIVE"


@dataclass(frozen=True, slots=True)
class Subscription:
    subscriber: str
    topics: frozenset[str]
    state: str = "ACTIVE_CONTRACT"
    authority_ceiling: str = "A1_INTERNAL"


class DependencyImpactRouter:
    """Route only dependency-affected nodes; this emits candidates, never effects."""

    def __init__(self, edges: Iterable[DependencyEdge], subscriptions: Iterable[Subscription]) -> None:
        self.edges = tuple(edges)
        self.subscriptions = tuple(subscriptions)

    def affected_nodes(self, roots: Iterable[str], max_depth: int = 5) -> tuple[str, ...]:
        seen = set(str(x) for x in roots)
        frontier = set(seen)
        for _ in range(max_depth):
            nxt: set[str] = set()
            for edge in self.edges:
                if not edge.state.startswith("ACTIVE") and "REGISTERED" not in edge.state:
                    continue
                if edge.from_node in frontier and edge.to_node not in seen:
                    nxt.add(edge.to_node)
                if edge.to_node in frontier and edge.from_node not in seen and edge.relation in {"SYNCS_WITH", "CANONICAL_STATE_STORED_IN", "WRITES_SURFACE_STATE_TO"}:
                    nxt.add(edge.from_node)
            if not nxt:
                break
            seen |= nxt
            frontier = nxt
        return tuple(sorted(seen))

    def route(self, event: EventEnvelope, roots: Iterable[str]) -> tuple[DispatchCandidate, ...]:
        affected = set(self.affected_nodes(roots))
        output: dict[tuple[str, str], DispatchCandidate] = {}
        for sub in self.subscriptions:
            if sub.state != "ACTIVE_CONTRACT":
                continue
            if event.topic not in sub.topics:
                continue
            if sub.subscriber not in affected and not sub.subscriber.startswith("ALL_"):
                continue
            key = (sub.subscriber, event.topic)
            output[key] = DispatchCandidate(
                target=sub.subscriber,
                topic=event.topic,
                reason=f"dependency-affected by {event.entity_id}/{event.event_type}",
                authority_ceiling=sub.authority_ceiling,
                effect="NONE",
            )
        return tuple(sorted(output.values(), key=lambda x: (x.target, x.topic)))
