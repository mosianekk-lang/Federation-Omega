from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class MissionIRError(ValueError):
    pass


class LaneClass(str, Enum):
    CRITICAL = "CRITICAL"
    PROVIDER = "PROVIDER"
    EVIDENCE = "EVIDENCE"
    COMPUTE = "COMPUTE"
    GOVERNANCE = "GOVERNANCE"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True)
class MissionNode:
    node_id: str
    operation: str
    lane: str
    lane_class: LaneClass
    depends_on: tuple[str, ...] = ()
    reversible: bool = True
    authority: str = "INTERNAL_REVERSIBLE"
    proof_obligations: tuple[str, ...] = ()
    expected_value: float = 1.0
    estimated_cost: float = 0.0
    estimated_latency_ms: int = 0
    risk: float = 0.0
    context_keys: tuple[str, ...] = ()

    @property
    def utility(self) -> float:
        latency_penalty = min(max(self.estimated_latency_ms, 0) / 100_000.0, 1.0)
        return self.expected_value - self.estimated_cost - self.risk - latency_penalty


@dataclass(frozen=True)
class MissionIR:
    mission_id: str
    objective: str
    success_condition: str
    authoritative_sources: tuple[str, ...]
    constraints: tuple[str, ...]
    nodes: tuple[MissionNode, ...]
    terminal_proofs: tuple[str, ...]
    compiled_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": "SLOS_MISSION_IR_V1",
            "mission_id": self.mission_id,
            "objective": self.objective,
            "success_condition": self.success_condition,
            "authoritative_sources": list(self.authoritative_sources),
            "constraints": list(self.constraints),
            "nodes": [
                {
                    "node_id": n.node_id,
                    "operation": n.operation,
                    "lane": n.lane,
                    "lane_class": n.lane_class.value,
                    "depends_on": list(n.depends_on),
                    "reversible": n.reversible,
                    "authority": n.authority,
                    "proof_obligations": list(n.proof_obligations),
                    "expected_value": n.expected_value,
                    "estimated_cost": n.estimated_cost,
                    "estimated_latency_ms": n.estimated_latency_ms,
                    "risk": n.risk,
                    "context_keys": list(n.context_keys),
                }
                for n in self.nodes
            ],
            "terminal_proofs": list(self.terminal_proofs),
            "compiled_digest": self.compiled_digest,
        }


@dataclass(frozen=True)
class ParallelWave:
    wave: int
    node_ids: tuple[str, ...]
    aggregate_utility: float


@dataclass(frozen=True)
class HyperSchedule:
    mission_id: str
    waves: tuple[ParallelWave, ...]
    critical_path: tuple[str, ...]
    max_parallelism: int
    suppressed_nodes: tuple[str, ...] = ()


class MissionCompiler:
    """Compile mission intent into a typed DAG and schedule independent work in parallel.

    The compiler is deterministic: same mission payload -> same digest/schedule. It does
    not execute effects and therefore cannot expand provider authority.
    """

    def compile(
        self,
        *,
        mission_id: str,
        objective: str,
        success_condition: str,
        nodes: Sequence[MissionNode],
        authoritative_sources: Iterable[str] = (),
        constraints: Iterable[str] = (),
        terminal_proofs: Iterable[str] = (),
    ) -> MissionIR:
        mission_id = mission_id.strip()
        objective = objective.strip()
        success_condition = success_condition.strip()
        if not mission_id or not objective or not success_condition:
            raise MissionIRError("mission_id, objective and success_condition are required")
        if not nodes:
            raise MissionIRError("MissionIR requires at least one node")

        ids = [n.node_id for n in nodes]
        if any(not value.strip() for value in ids) or len(set(ids)) != len(ids):
            raise MissionIRError("node ids must be non-empty and unique")
        idset = set(ids)
        for node in nodes:
            missing = set(node.depends_on) - idset
            if missing:
                raise MissionIRError(f"{node.node_id} has unknown dependencies: {sorted(missing)}")
            if node.node_id in node.depends_on:
                raise MissionIRError(f"{node.node_id} depends on itself")
            if not 0.0 <= node.risk <= 1.0:
                raise MissionIRError(f"risk outside [0,1] for {node.node_id}")
            if not node.reversible and node.authority == "INTERNAL_REVERSIBLE":
                raise MissionIRError(f"irreversible node {node.node_id} requires elevated authority class")

        self._topological(ids, {n.node_id: n.depends_on for n in nodes})
        payload = {
            "mission_id": mission_id,
            "objective": objective,
            "success_condition": success_condition,
            "sources": sorted(set(authoritative_sources)),
            "constraints": sorted(set(constraints)),
            "terminal_proofs": sorted(set(terminal_proofs)),
            "nodes": [
                {
                    "node_id": n.node_id,
                    "operation": n.operation,
                    "lane": n.lane,
                    "lane_class": n.lane_class.value,
                    "depends_on": list(n.depends_on),
                    "reversible": n.reversible,
                    "authority": n.authority,
                    "proof_obligations": list(n.proof_obligations),
                    "expected_value": n.expected_value,
                    "estimated_cost": n.estimated_cost,
                    "estimated_latency_ms": n.estimated_latency_ms,
                    "risk": n.risk,
                    "context_keys": list(n.context_keys),
                }
                for n in sorted(nodes, key=lambda x: x.node_id)
            ],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return MissionIR(
            mission_id=mission_id,
            objective=objective,
            success_condition=success_condition,
            authoritative_sources=tuple(sorted(set(authoritative_sources))),
            constraints=tuple(sorted(set(constraints))),
            nodes=tuple(nodes),
            terminal_proofs=tuple(sorted(set(terminal_proofs))),
            compiled_digest=digest,
        )

    def schedule(self, ir: MissionIR, *, max_parallelism: int = 8, min_utility: float = -1e9) -> HyperSchedule:
        if max_parallelism < 1:
            raise MissionIRError("max_parallelism must be >= 1")
        node_map = {n.node_id: n for n in ir.nodes}
        active = {nid for nid, node in node_map.items() if node.utility >= min_utility}
        suppressed = tuple(sorted(set(node_map) - active))
        # Never suppress a dependency of an active node. Promote it back into the schedule.
        changed = True
        while changed:
            changed = False
            for nid in tuple(active):
                for dep in node_map[nid].depends_on:
                    if dep not in active:
                        active.add(dep)
                        changed = True
        suppressed = tuple(sorted(set(node_map) - active))

        done: set[str] = set()
        waves: list[ParallelWave] = []
        wave_no = 0
        while done != active:
            ready = [
                node_map[nid]
                for nid in active - done
                if set(node_map[nid].depends_on).issubset(done)
            ]
            if not ready:
                raise MissionIRError("active graph is cyclic or unschedulable")
            # Hyperperformance priority: critical/provider/evidence first, then value density.
            lane_rank = {
                LaneClass.CRITICAL: 0,
                LaneClass.PROVIDER: 1,
                LaneClass.EVIDENCE: 2,
                LaneClass.GOVERNANCE: 3,
                LaneClass.COMPUTE: 4,
                LaneClass.RECOVERY: 5,
            }
            ready.sort(key=lambda n: (lane_rank[n.lane_class], -n.utility, n.estimated_latency_ms, n.node_id))
            chosen = ready[:max_parallelism]
            waves.append(
                ParallelWave(
                    wave=wave_no,
                    node_ids=tuple(n.node_id for n in chosen),
                    aggregate_utility=sum(n.utility for n in chosen),
                )
            )
            done.update(n.node_id for n in chosen)
            wave_no += 1

        return HyperSchedule(
            mission_id=ir.mission_id,
            waves=tuple(waves),
            critical_path=self._critical_path(ir),
            max_parallelism=max_parallelism,
            suppressed_nodes=suppressed,
        )

    @staticmethod
    def _topological(ids: Sequence[str], deps: Mapping[str, Sequence[str]]) -> list[str]:
        remaining = set(ids)
        done: set[str] = set()
        order: list[str] = []
        while remaining:
            ready = sorted(nid for nid in remaining if set(deps[nid]).issubset(done))
            if not ready:
                raise MissionIRError("mission dependency cycle detected")
            for nid in ready:
                remaining.remove(nid)
                done.add(nid)
                order.append(nid)
        return order

    @staticmethod
    def _critical_path(ir: MissionIR) -> tuple[str, ...]:
        node_map = {n.node_id: n for n in ir.nodes}
        order = MissionCompiler._topological(list(node_map), {k: v.depends_on for k, v in node_map.items()})
        best_cost: dict[str, float] = {}
        path: dict[str, tuple[str, ...]] = {}
        for nid in order:
            node = node_map[nid]
            own = max(node.estimated_latency_ms, 1)
            if not node.depends_on:
                best_cost[nid] = own
                path[nid] = (nid,)
                continue
            parent = max(node.depends_on, key=lambda d: best_cost[d])
            best_cost[nid] = best_cost[parent] + own
            path[nid] = path[parent] + (nid,)
        terminal = max(order, key=lambda nid: best_cost[nid])
        return path[terminal]


__all__ = [
    "HyperSchedule",
    "LaneClass",
    "MissionCompiler",
    "MissionIR",
    "MissionIRError",
    "MissionNode",
    "ParallelWave",
]
