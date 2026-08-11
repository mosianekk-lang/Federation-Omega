from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyNode:
    id: str
    blocked: bool = False
    effort: float = 0.5


class DependencyCentrality:
    """Rank blockers by downstream unlock leverage.

    Edges are (upstream, downstream). Resolving an upstream node may unlock all
    reachable downstream nodes. Scores are deterministic and bounded.
    """

    def __init__(self, nodes: tuple[DependencyNode, ...], edges: tuple[tuple[str, str], ...]) -> None:
        self.nodes = {node.id: node for node in nodes}
        self.children: dict[str, set[str]] = {node.id: set() for node in nodes}
        for upstream, downstream in edges:
            if upstream not in self.nodes or downstream not in self.nodes:
                raise KeyError("dependency edges must reference registered nodes")
            self.children[upstream].add(downstream)

    def downstream(self, node_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        stack = list(self.children.get(node_id, ()))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.children.get(current, ()))
        return tuple(sorted(seen))

    def unlock_score(self, node_id: str) -> float:
        node = self.nodes[node_id]
        reachable = len(self.downstream(node_id))
        effort = max(0.05, min(1.0, node.effort))
        blocked_bonus = 1.25 if node.blocked else 1.0
        return round((reachable + 1) * blocked_bonus / effort, 6)

    def ranked_blockers(self) -> tuple[tuple[str, float], ...]:
        candidates = [node for node in self.nodes.values() if node.blocked]
        return tuple(
            sorted(
                ((node.id, self.unlock_score(node.id)) for node in candidates),
                key=lambda item: (-item[1], item[0]),
            )
        )
