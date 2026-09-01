from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from .mission_ir import MissionIR


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


class TwinError(RuntimeError):
    pass


class TwinNodeKind(str, Enum):
    MISSION = "MISSION"
    CAPABILITY = "CAPABILITY"
    PROVIDER = "PROVIDER"
    ARTIFACT = "ARTIFACT"
    AUTHORITY = "AUTHORITY"
    PROOF = "PROOF"
    RUNTIME = "RUNTIME"
    WORKER = "WORKER"


@dataclass(frozen=True)
class TwinNode:
    node_id: str
    kind: TwinNodeKind
    state: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TwinEdge:
    source: str
    relation: str
    target: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Intervention:
    intervention_id: str
    description: str
    state_patch: Mapping[str, Mapping[str, Any]]
    expected_value: float
    uncertainty_reduction: float
    risk: float
    cost: float
    latency_ms: float
    reversible: bool = True
    provider_effect_required: bool = False


@dataclass(frozen=True)
class SimulationResult:
    intervention_id: str
    target_match_ratio: float
    expected_value: float
    uncertainty_reduction: float
    risk: float
    cost: float
    latency_ms: float
    reversible: bool
    provider_effect_performed: bool
    score: float
    simulated_snapshot_sha256: str


class FederationDigitalTwin:
    """Side-effect-free state graph for planning and counterfactual evaluation."""

    def __init__(self) -> None:
        self._nodes: dict[str, TwinNode] = {}
        self._edges: dict[tuple[str, str, str], TwinEdge] = {}
        self._events: list[dict[str, Any]] = []

    def upsert_node(self, node: TwinNode) -> None:
        if not node.node_id.strip():
            raise TwinError("TWIN_NODE_ID_REQUIRED")
        self._nodes[node.node_id] = node
        self._events.append(
            {
                "kind": "NODE_UPSERT",
                "node_id": node.node_id,
                "node_kind": node.kind.value,
                "state_sha256": _digest(dict(node.state)),
            }
        )

    def add_edge(self, edge: TwinEdge) -> None:
        if edge.source not in self._nodes or edge.target not in self._nodes:
            raise TwinError("TWIN_EDGE_ENDPOINT_MISSING")
        key = (edge.source, edge.relation, edge.target)
        self._edges[key] = edge
        self._events.append(
            {
                "kind": "EDGE_UPSERT",
                "source": edge.source,
                "relation": edge.relation,
                "target": edge.target,
            }
        )

    def project_mission(self, mission: MissionIR) -> None:
        self.upsert_node(
            TwinNode(
                node_id=f"mission:{mission.mission_id}",
                kind=TwinNodeKind.MISSION,
                state={
                    "objective": mission.objective,
                    "initial_state": dict(mission.initial_state),
                    "target_state": dict(mission.target_state),
                    "compiled_sha256": mission.compiled_sha256,
                },
            )
        )

    def observe(self, node_id: str, patch: Mapping[str, Any], *, evidence_ref: str) -> None:
        if node_id not in self._nodes:
            raise TwinError(f"TWIN_NODE_UNKNOWN:{node_id}")
        if not evidence_ref.strip():
            raise TwinError("OBSERVATION_EVIDENCE_REF_REQUIRED")
        prior = self._nodes[node_id]
        state = dict(prior.state)
        state.update(dict(patch))
        self._nodes[node_id] = TwinNode(node_id=node_id, kind=prior.kind, state=state)
        self._events.append(
            {
                "kind": "OBSERVATION",
                "node_id": node_id,
                "patch_sha256": _digest(dict(patch)),
                "evidence_ref": evidence_ref,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        body = {
            "schema": "FEDERATION_DIGITAL_TWIN_V1",
            "nodes": [
                {
                    "node_id": node.node_id,
                    "kind": node.kind.value,
                    "state": dict(node.state),
                }
                for node in sorted(self._nodes.values(), key=lambda item: item.node_id)
            ],
            "edges": [
                {
                    "source": edge.source,
                    "relation": edge.relation,
                    "target": edge.target,
                    "attributes": dict(edge.attributes),
                }
                for edge in sorted(
                    self._edges.values(),
                    key=lambda item: (item.source, item.relation, item.target),
                )
            ],
            "events": list(self._events),
        }
        return body | {"snapshot_sha256": _digest(body), "provider_effect_performed": False}

    def clone(self) -> "FederationDigitalTwin":
        other = FederationDigitalTwin()
        other._nodes = copy.deepcopy(self._nodes)
        other._edges = copy.deepcopy(self._edges)
        other._events = copy.deepcopy(self._events)
        return other

    @staticmethod
    def _target_match(current: Mapping[str, Any], target: Mapping[str, Any]) -> float:
        if not target:
            return 1.0
        matches = sum(1 for key, value in target.items() if current.get(key) == value)
        return matches / len(target)

    def simulate(self, mission: MissionIR, intervention: Intervention) -> SimulationResult:
        if intervention.provider_effect_required:
            # The twin records the hypothetical provider requirement but never executes it.
            pass
        if not 0.0 <= intervention.risk <= 1.0:
            raise TwinError("INTERVENTION_RISK_OUT_OF_RANGE")
        if not 0.0 <= intervention.uncertainty_reduction <= 1.0:
            raise TwinError("INTERVENTION_UNCERTAINTY_OUT_OF_RANGE")
        if intervention.cost < 0 or intervention.latency_ms <= 0:
            raise TwinError("INTERVENTION_ECONOMICS_INVALID")

        shadow = self.clone()
        mission_node_id = f"mission:{mission.mission_id}"
        if mission_node_id not in shadow._nodes:
            shadow.project_mission(mission)
        for node_id, patch in intervention.state_patch.items():
            if node_id not in shadow._nodes:
                shadow.upsert_node(
                    TwinNode(node_id=node_id, kind=TwinNodeKind.RUNTIME, state=dict(patch))
                )
            else:
                prior = shadow._nodes[node_id]
                state = dict(prior.state)
                state.update(dict(patch))
                shadow._nodes[node_id] = TwinNode(node_id=node_id, kind=prior.kind, state=state)
            shadow._events.append(
                {
                    "kind": "SIMULATED_PATCH",
                    "intervention_id": intervention.intervention_id,
                    "node_id": node_id,
                    "patch_sha256": _digest(dict(patch)),
                }
            )

        mission_node = shadow._nodes[mission_node_id]
        mission_state = dict(mission.initial_state)
        mission_patch = intervention.state_patch.get(mission_node_id, {})
        mission_state.update(dict(mission_patch))
        match = self._target_match(mission_state, mission.target_state)
        score = (
            3.0 * match
            + 1.5 * intervention.expected_value
            + 1.25 * intervention.uncertainty_reduction
            - 1.75 * intervention.risk
            - 0.20 * intervention.cost
            - 0.10 * (intervention.latency_ms / 1000.0)
            + (0.20 if intervention.reversible else 0.0)
        )
        snapshot = shadow.snapshot()
        return SimulationResult(
            intervention_id=intervention.intervention_id,
            target_match_ratio=match,
            expected_value=intervention.expected_value,
            uncertainty_reduction=intervention.uncertainty_reduction,
            risk=intervention.risk,
            cost=intervention.cost,
            latency_ms=intervention.latency_ms,
            reversible=intervention.reversible,
            provider_effect_performed=False,
            score=score,
            simulated_snapshot_sha256=snapshot["snapshot_sha256"],
        )


class CounterfactualController:
    """Ranks interventions against a no-action baseline without touching providers."""

    def __init__(self, twin: FederationDigitalTwin):
        self.twin = twin

    def rank(
        self,
        mission: MissionIR,
        interventions: Sequence[Intervention],
    ) -> tuple[SimulationResult, ...]:
        baseline = Intervention(
            intervention_id="NO_ACTION",
            description="Counterfactual baseline",
            state_patch={},
            expected_value=0.0,
            uncertainty_reduction=0.0,
            risk=0.0,
            cost=0.0,
            latency_ms=1.0,
            reversible=True,
            provider_effect_required=False,
        )
        results = [self.twin.simulate(mission, baseline)]
        results.extend(self.twin.simulate(mission, item) for item in interventions)
        return tuple(
            sorted(
                results,
                key=lambda item: (
                    -item.score,
                    -item.target_match_ratio,
                    item.risk,
                    item.cost,
                    item.latency_ms,
                    item.intervention_id,
                ),
            )
        )


__all__ = [
    "CounterfactualController",
    "FederationDigitalTwin",
    "Intervention",
    "SimulationResult",
    "TwinEdge",
    "TwinError",
    "TwinNode",
    "TwinNodeKind",
]
