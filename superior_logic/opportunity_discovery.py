from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .digital_twin import FederationDigitalTwin
from .mission_ir import MissionIR


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    kind: str
    description: str
    expected_leverage: float
    evidence: tuple[str, ...]
    safe_next_action: str


class OpportunityDiscoveryEngine:
    """Detect capability gaps and mission bottlenecks without dispatch authority."""

    def discover(
        self,
        *,
        twin: FederationDigitalTwin,
        missions: Sequence[MissionIR] = (),
        required_capabilities: Iterable[tuple[str, str]] = (),
    ) -> tuple[Opportunity, ...]:
        found: list[Opportunity] = []
        for operation, target_class in twin.opportunity_gaps(required_capabilities):
            found.append(
                Opportunity(
                    opportunity_id=f"CAPABILITY_GAP:{operation}:{target_class}",
                    kind="CAPABILITY_GAP",
                    description=f"No available capability satisfies {operation} on {target_class}",
                    expected_leverage=0.9,
                    evidence=(f"missing:{operation}:{target_class}",),
                    safe_next_action="SEARCH_REUSABLE_CAPABILITY",
                )
            )

        for mission in missions:
            if not mission.nodes:
                continue
            longest = max(mission.nodes, key=lambda n: (n.estimated_latency_ms, n.node_id))
            if longest.estimated_latency_ms >= 50_000:
                found.append(
                    Opportunity(
                        opportunity_id=f"LATENCY:{mission.mission_id}:{longest.node_id}",
                        kind="LATENCY_BOTTLENECK",
                        description=f"Mission {mission.mission_id} is dominated by {longest.node_id}",
                        expected_leverage=min(longest.estimated_latency_ms / 100_000.0, 1.0),
                        evidence=(f"latency_ms:{longest.estimated_latency_ms}", f"node:{longest.node_id}"),
                        safe_next_action="HYPERCUBE_RESOLVE_BOTTLENECK",
                    )
                )
            high_risk = tuple(sorted(n.node_id for n in mission.nodes if n.risk >= 0.7))
            if high_risk:
                found.append(
                    Opportunity(
                        opportunity_id=f"RISK:{mission.mission_id}",
                        kind="REVERSIBILITY_OR_RISK_GAP",
                        description=f"Mission {mission.mission_id} contains high-risk nodes",
                        expected_leverage=0.85,
                        evidence=tuple(f"high_risk_node:{nid}" for nid in high_risk),
                        safe_next_action="HYPERCUBE_HARVEST_REVERSIBLE_ROUTES",
                    )
                )

            # Hypercube deep-seek extensions: search for constraints that are not
            # represented by the single slowest/highest-risk node.
            by_id = {node.node_id: node for node in mission.nodes}
            depth_cache: dict[str, int] = {}

            def depth(node_id: str) -> int:
                if node_id in depth_cache:
                    return depth_cache[node_id]
                deps = by_id[node_id].depends_on
                value = 1 if not deps else 1 + max(depth(dep) for dep in deps)
                depth_cache[node_id] = value
                return value

            max_depth = max((depth(node.node_id) for node in mission.nodes), default=0)
            total_latency = sum(max(0, node.estimated_latency_ms) for node in mission.nodes)
            critical_latency = max(
                (
                    max(0, node.estimated_latency_ms) * depth(node.node_id)
                    for node in mission.nodes
                ),
                default=0,
            )
            if max_depth >= 4:
                found.append(
                    Opportunity(
                        opportunity_id=f"SERIAL:{mission.mission_id}",
                        kind="SERIAL_DEPENDENCY_BOTTLENECK",
                        description=f"Mission {mission.mission_id} has dependency depth {max_depth}",
                        expected_leverage=min(0.55 + 0.07 * max_depth, 1.0),
                        evidence=(
                            f"dependency_depth:{max_depth}",
                            f"total_latency_ms:{total_latency}",
                            f"weighted_critical_latency:{critical_latency}",
                        ),
                        safe_next_action="HYPERCUBE_COMPILE_PARALLEL_OR_STACK_AWARE_ROUTE",
                    )
                )

            proof_nodes = tuple(
                node
                for node in mission.nodes
                if node.proof_obligations
            )
            proof_latency = sum(max(0, node.estimated_latency_ms) for node in proof_nodes)
            if len(proof_nodes) >= 2 and proof_latency >= 40_000:
                found.append(
                    Opportunity(
                        opportunity_id=f"PROOF:{mission.mission_id}",
                        kind="PROOF_EVIDENCE_BOTTLENECK",
                        description=f"Mission {mission.mission_id} has proof-heavy critical work",
                        expected_leverage=min(0.55 + proof_latency / 250_000.0, 1.0),
                        evidence=tuple(
                            [f"proof_latency_ms:{proof_latency}"]
                            + [f"proof_node:{node.node_id}" for node in proof_nodes]
                        ),
                        safe_next_action="HYPERCUBE_HARVEST_PROOF_CACHE_IMPACT_AND_READBACK_ROUTES",
                    )
                )

            total_cost = sum(max(0.0, float(node.estimated_cost)) for node in mission.nodes)
            if total_cost > 0:
                costliest = max(mission.nodes, key=lambda node: (node.estimated_cost, node.node_id))
                cost_share = max(0.0, float(costliest.estimated_cost)) / total_cost
                if total_cost >= 1.0 and cost_share >= 0.5:
                    found.append(
                        Opportunity(
                            opportunity_id=f"COST:{mission.mission_id}:{costliest.node_id}",
                            kind="COST_RESOURCE_BOTTLENECK",
                            description=f"Mission {mission.mission_id} cost is concentrated in {costliest.node_id}",
                            expected_leverage=min(0.45 + 0.45 * cost_share, 1.0),
                            evidence=(
                                f"total_cost:{total_cost:.6f}",
                                f"cost_share:{cost_share:.6f}",
                                f"node:{costliest.node_id}",
                            ),
                            safe_next_action="HYPERCUBE_HARVEST_CACHE_REMOTE_EXECUTION_AND_RESOURCE_ROUTES",
                        )
                    )

            elevated = tuple(
                sorted(
                    node.node_id
                    for node in mission.nodes
                    if not node.reversible or node.authority != "INTERNAL_REVERSIBLE"
                )
            )
            if len(elevated) >= 2:
                found.append(
                    Opportunity(
                        opportunity_id=f"AUTHORITY:{mission.mission_id}",
                        kind="AUTHORITY_BOTTLENECK",
                        description=f"Mission {mission.mission_id} has multiple elevated-authority stages",
                        expected_leverage=min(0.50 + 0.08 * len(elevated), 1.0),
                        evidence=tuple(f"authority_node:{node_id}" for node_id in elevated),
                        safe_next_action="HYPERCUBE_HARVEST_LEASE_PREFLIGHT_AND_REVERSIBLE_PRECURSOR_ROUTES",
                    )
                )

            operation_groups: dict[tuple[str, str], list[str]] = {}
            for node in mission.nodes:
                operation_groups.setdefault((node.operation, node.lane), []).append(node.node_id)
            duplicated = tuple(
                sorted(
                    f"{operation}:{lane}:{','.join(sorted(node_ids))}"
                    for (operation, lane), node_ids in operation_groups.items()
                    if len(node_ids) >= 3
                )
            )
            if duplicated:
                found.append(
                    Opportunity(
                        opportunity_id=f"DUPLICATION:{mission.mission_id}",
                        kind="ARCHITECTURAL_DUPLICATION_BOTTLENECK",
                        description=f"Mission {mission.mission_id} repeats equivalent operation/lane patterns",
                        expected_leverage=0.72,
                        evidence=tuple(f"duplicate_group:{item}" for item in duplicated),
                        safe_next_action="HYPERCUBE_COMPOSE_OR_RETIRE_REDUNDANT_PATHS",
                    )
                )

        found.sort(key=lambda row: (-row.expected_leverage, row.opportunity_id))
        return tuple(found)


__all__ = ["Opportunity", "OpportunityDiscoveryEngine"]
