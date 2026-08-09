from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineageNode:
    id: str
    kind: str
    proof_state: str


@dataclass
class LineageGraph:
    nodes: dict[str, LineageNode] = field(default_factory=dict)
    parents: dict[str, set[str]] = field(default_factory=dict)

    def add_node(self, node: LineageNode) -> None:
        self.nodes[node.id] = node
        self.parents.setdefault(node.id, set())

    def link(self, parent_id: str, child_id: str) -> None:
        if parent_id not in self.nodes or child_id not in self.nodes:
            raise KeyError("Both lineage nodes must exist before linking")
        if parent_id == child_id:
            raise ValueError("Self-lineage is not permitted")
        self.parents.setdefault(child_id, set()).add(parent_id)
        if self._has_cycle(child_id, child_id, set()):
            self.parents[child_id].remove(parent_id)
            raise ValueError("Circular reasoning/evidence lineage is not permitted")

    def ancestors(self, node_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        stack = list(self.parents.get(node_id, set()))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.parents.get(current, set()))
        return tuple(sorted(seen))

    def source_roots(self, node_id: str) -> tuple[str, ...]:
        roots = []
        for ancestor_id in self.ancestors(node_id):
            node = self.nodes[ancestor_id]
            if not self.parents.get(ancestor_id) and node.kind == "EVIDENCE":
                roots.append(ancestor_id)
        return tuple(sorted(roots))

    def affected_descendants(self, changed_id: str) -> tuple[str, ...]:
        descendants: set[str] = set()
        frontier = [changed_id]
        while frontier:
            parent = frontier.pop()
            for child, parents in self.parents.items():
                if parent in parents and child not in descendants:
                    descendants.add(child)
                    frontier.append(child)
        return tuple(sorted(descendants))

    def _has_cycle(self, current: str, target: str, seen: set[str]) -> bool:
        if current in seen:
            return False
        seen.add(current)
        for parent in self.parents.get(current, set()):
            if parent == target:
                return True
            if self._has_cycle(parent, target, seen):
                return True
        return False
