from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class CausalNode:
    node_id: str
    kind: str = "generic"
    valid: bool = True
    invalidation_reason: str = ""


class CausalImpactGraph:
    """Minimal causal/dependency graph for proof invalidation.

    Edges mean target depends on source. Invalidating a source recursively
    invalidates downstream summaries, decisions, artifacts and maturity claims.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, CausalNode] = {}
        self._downstream: dict[str, set[str]] = defaultdict(set)
        self._upstream: dict[str, set[str]] = defaultdict(set)

    def add_node(self, node_id: str, kind: str = "generic") -> CausalNode:
        return self.nodes.setdefault(node_id, CausalNode(node_id, kind))

    def add_dependency(self, source: str, target: str) -> None:
        self.add_node(source)
        self.add_node(target)
        self._downstream[source].add(target)
        self._upstream[target].add(source)

    def downstream(self, node_id: str) -> Tuple[str, ...]:
        return tuple(sorted(self._downstream.get(node_id, ())))

    def invalidate(self, node_id: str, reason: str) -> Tuple[str, ...]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        affected = []
        queue = deque([node_id])
        seen = set()
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            node = self.nodes[current]
            node.valid = False
            node.invalidation_reason = (
                reason if current == node_id else f"upstream invalidated: {node_id}"
            )
            affected.append(current)
            queue.extend(sorted(self._downstream.get(current, ())))
        return tuple(affected)

    def revalidate(self, node_id: str) -> None:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        invalid_upstream = [
            source for source in self._upstream.get(node_id, ()) if not self.nodes[source].valid
        ]
        if invalid_upstream:
            raise RuntimeError(
                f"cannot revalidate {node_id}; invalid upstream: {sorted(invalid_upstream)}"
            )
        node = self.nodes[node_id]
        node.valid = True
        node.invalidation_reason = ""
