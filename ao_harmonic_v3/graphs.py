from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Mission, MissionNode, NodeState, ProofNode, TruthState


@dataclass
class StateRecord:
    state_key: str
    immutable_events: list[dict[str, Any]] = field(default_factory=list)
    current_projection: dict[str, Any] = field(default_factory=dict)
    derived_interpretation: dict[str, Any] = field(default_factory=dict)
    supersession_lineage: dict[str, list[str]] = field(
        default_factory=lambda: {"supersedes": [], "superseded_by": []}
    )


class StateFabric:
    """Three-layer state: immutable events, current projection, interpretation."""

    def __init__(self) -> None:
        self._states: dict[str, StateRecord] = {}

    def ensure(self, state_key: str) -> StateRecord:
        return self._states.setdefault(state_key, StateRecord(state_key=state_key))

    def append_event(self, state_key: str, event: dict[str, Any]) -> None:
        self.ensure(state_key).immutable_events.append(dict(event))

    def project(
        self,
        state_key: str,
        *,
        value: Any,
        source: str,
        verified_at: str,
        status: str,
    ) -> None:
        self.ensure(state_key).current_projection = {
            "value": value,
            "source": source,
            "verified_at": verified_at,
            "status": status,
        }

    def interpret(
        self,
        state_key: str,
        *,
        meaning: str,
        owner_system: str,
        basis: list[str],
        version: str,
    ) -> None:
        self.ensure(state_key).derived_interpretation = {
            "meaning": meaning,
            "owner_system": owner_system,
            "basis": list(basis),
            "version": version,
        }

    def get(self, state_key: str) -> StateRecord | None:
        return self._states.get(state_key)


class MissionGraph:
    def __init__(self) -> None:
        self.missions: dict[str, Mission] = {}

    def add_mission(self, mission: Mission) -> None:
        self.missions[mission.mission_id] = mission

    def add_node(self, mission_id: str, node: MissionNode) -> None:
        self.missions[mission_id].nodes[node.node_id] = node

    def dependency_satisfied(self, mission: Mission, node: MissionNode) -> bool:
        return all(
            mission.nodes.get(dep) is not None
            and mission.nodes[dep].status == NodeState.DONE
            for dep in node.dependencies
        )

    def ready_nodes(self, mission_id: str) -> list[MissionNode]:
        mission = self.missions[mission_id]
        return [
            node
            for node in mission.nodes.values()
            if node.status == NodeState.READY and self.dependency_satisfied(mission, node)
        ]

    def block_node(self, mission_id: str, node_id: str, reason: str) -> None:
        node = self.missions[mission_id].nodes[node_id]
        node.status = NodeState.BLOCKED
        if reason not in node.blockers:
            node.blockers.append(reason)


class ProofGraph:
    """Directed dependency graph supporting reverse impact propagation."""

    def __init__(self) -> None:
        self.nodes: dict[str, ProofNode] = {}

    def add(self, node: ProofNode) -> None:
        self.nodes[node.proof_node_id] = node

    def direct_dependants(self, proof_node_id: str) -> list[ProofNode]:
        return [n for n in self.nodes.values() if proof_node_id in n.depends_on]

    def descendants(self, proof_node_id: str) -> list[ProofNode]:
        seen: set[str] = set()
        queue = [proof_node_id]
        out: list[ProofNode] = []
        while queue:
            parent = queue.pop(0)
            for child in self.direct_dependants(parent):
                if child.proof_node_id in seen:
                    continue
                seen.add(child.proof_node_id)
                out.append(child)
                queue.append(child.proof_node_id)
        return out

    def downgrade(
        self,
        proof_node_id: str,
        *,
        new_status: TruthState,
        confidence: float,
    ) -> list[ProofNode]:
        node = self.nodes[proof_node_id]
        node.verification_status = new_status
        node.confidence = confidence
        return self.descendants(proof_node_id)
