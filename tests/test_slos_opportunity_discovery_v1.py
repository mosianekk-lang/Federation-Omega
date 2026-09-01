from __future__ import annotations

import unittest

from superior_logic.digital_twin import CapabilityEdge, FederationDigitalTwin
from superior_logic.mission_ir import LaneClass, MissionCompiler, MissionNode
from superior_logic.opportunity_discovery import OpportunityDiscoveryEngine


class OpportunityDiscoveryTests(unittest.TestCase):
    def test_discovers_missing_capability_latency_and_risk(self) -> None:
        twin = FederationDigitalTwin()
        twin.upsert(CapabilityEdge("read", "GITHUB", "READ", "REPO", "READ_ONLY", 1.0, 5, 0.0, 0.0, True))
        mission = MissionCompiler().compile(
            mission_id="M-OPP",
            objective="complete safely",
            success_condition="verified",
            nodes=(
                MissionNode("slow", "slow provider step", "provider", LaneClass.PROVIDER, estimated_latency_ms=80000, risk=0.1),
                MissionNode("risky", "risky step", "provider", LaneClass.CRITICAL, depends_on=("slow",), reversible=False, authority="PROVIDER_MUTATION", risk=0.8),
            ),
        )
        opportunities = OpportunityDiscoveryEngine().discover(
            twin=twin,
            missions=(mission,),
            required_capabilities=(("READ", "REPO"), ("WRITE", "REPO")),
        )
        kinds = {item.kind for item in opportunities}
        self.assertEqual(kinds, {"CAPABILITY_GAP", "LATENCY_BOTTLENECK", "REVERSIBILITY_OR_RISK_GAP"})
        self.assertTrue(all(item.safe_next_action for item in opportunities))


if __name__ == "__main__":
    unittest.main()
