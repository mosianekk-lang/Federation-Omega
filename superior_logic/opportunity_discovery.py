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
                        safe_next_action="SHADOW_ALTERNATIVE_ROUTE",
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
                        safe_next_action="SEARCH_REVERSIBLE_PRECURSOR",
                    )
                )

        found.sort(key=lambda row: (-row.expected_leverage, row.opportunity_id))
        return tuple(found)


__all__ = ["Opportunity", "OpportunityDiscoveryEngine"]
