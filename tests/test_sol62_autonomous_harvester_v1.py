from __future__ import annotations

import asyncio
import unittest

from services.sol62_client_runtime.autonomous_harvester import FuseAutonomousHarvester


class FuseAutonomousHarvesterTests(unittest.TestCase):
    def test_gap_compiles_hypercube_codeforge_build_packet(self):
        harvester = FuseAutonomousHarvester(source_frontier="abc123")
        result = asyncio.run(
            harvester.harvest(
                mission_id="m1",
                transition_id="t1",
                objective="complete the FUSE mission",
                reason="NO_QUALIFIED_ROUTE",
            )
        )
        self.assertTrue(result.build_required)
        self.assertEqual(result.build_packet["task_type"], "SOL62_CLIENT_BUILD")
        self.assertEqual(result.build_packet["source_frontier"], "abc123")
        self.assertIn("hypercube", result.build_packet)
        self.assertIn("codeforge", result.build_packet)
        self.assertIn("idea_system", result.build_packet)
        self.assertIn("asia_frontier_p0", result.build_packet)
        self.assertEqual(result.build_packet["asia_frontier_p0"]["mechanism_count"], 6)
        self.assertFalse(result.build_packet["asia_frontier_p0"]["market_superiority_proven"])
        self.assertFalse(result.build_packet["authority_boundary"]["source_mutation_authority_granted"])
        self.assertFalse(result.build_packet["authority_boundary"]["provider_effect_authority_granted"])

    def test_transition_binding_gap_is_encoded_as_residual(self):
        harvester = FuseAutonomousHarvester(source_frontier="abc123")
        result = asyncio.run(
            harvester.harvest(
                mission_id="m1",
                transition_id="t1",
                objective="complete",
                reason="TRANSITION_EXECUTION_BINDING_MISSING",
            )
        )
        self.assertTrue(result.build_required)
        decisions = result.build_packet["idea_system"]["capability_decisions"]
        self.assertTrue(decisions)


if __name__ == "__main__":
    unittest.main()
