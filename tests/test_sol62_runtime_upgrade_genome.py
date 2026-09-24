from __future__ import annotations

import asyncio
import unittest

from services.sol62_client_runtime.autonomous_harvester import FuseAutonomousHarvester
from services.sol62_client_runtime.runtime_upgrade_genome import (
    GENOME_SCHEMA,
    UPGRADE_GENOME,
    genome_summary,
    select_upgrade_genes,
)


class Sol62RuntimeUpgradeGenomeTests(unittest.TestCase):
    def test_genome_is_124_unique_monotonic_genes(self):
        ids = [gene.gene_id for gene in UPGRADE_GENOME]
        self.assertEqual(len(ids), 124)
        self.assertEqual(len(set(ids)), 100)
        self.assertEqual(ids[0], "HG-SOL62-101")
        self.assertEqual(ids[-1], "HG-SOL62-224")
        self.assertEqual(genome_summary()["schema"], GENOME_SCHEMA)

    def test_genes_are_candidate_residuals_not_maturity_promotions(self):
        self.assertTrue(all(gene.maturity == "CANDIDATE_RESIDUAL" for gene in UPGRADE_GENOME))
        self.assertTrue(all(gene.provenance for gene in UPGRADE_GENOME))
        boundary = genome_summary()["truth_boundary"]
        self.assertIn("GENOME_REGISTERED_NE_IMPLEMENTED", boundary)
        self.assertIn("SOURCE_ADMITTED_NE_LIVE_RUNTIME", boundary)

    def test_failure_specific_selection_prioritizes_matching_mechanisms(self):
        selected = select_upgrade_genes(
            objective="recover a stalled consumer while preserving mission identity",
            reason="queue lag and pending consumer lease recovery",
            limit=8,
        )
        self.assertTrue(selected)
        tags = {tag for gene in selected for tag in gene.tags}
        self.assertTrue({"lag", "consumer", "lease", "recovery"} & tags)

    def test_no_match_uses_balanced_deterministic_fallback(self):
        selected = select_upgrade_genes(
            objective="unseen novel residual",
            reason="ZXQJ_UNSEEN_REASON",
            limit=10,
        )
        self.assertEqual(len(selected), 10)
        self.assertEqual(len({gene.category for gene in selected}), 10)

    def test_harvester_embeds_ranked_genome_without_granting_authority(self):
        packet = asyncio.run(
            FuseAutonomousHarvester(source_frontier="abc123").harvest(
                mission_id="m1",
                transition_id="t1",
                objective="recover queue lag and provider failover",
                reason="QUALIFIED_ROUTES_EXHAUSTED",
            )
        ).build_packet
        genome = packet["runtime_upgrade_genome"]
        self.assertEqual(genome["summary"]["count"], 124)
        self.assertGreater(len(genome["selected"]), 0)
        self.assertLessEqual(len(genome["selected"]), 12)
        self.assertEqual(genome["selection_semantic"], "RANKED_CANDIDATE_RESIDUALS_ONLY")
        self.assertFalse(packet["authority_boundary"]["source_mutation_authority_granted"])
        self.assertFalse(packet["authority_boundary"]["provider_effect_authority_granted"])


    def test_frontier_residuals_include_stream_survival_and_private_tool_bridging(self):
        by_id = {gene.gene_id: gene for gene in UPGRADE_GENOME}
        self.assertEqual(by_id["HG-SOL62-201"].mechanism, "detached_background_response_execution")
        self.assertEqual(by_id["HG-SOL62-211"].mechanism, "secure_mcp_tunnel_private_bridge")
        self.assertEqual(by_id["HG-SOL62-217"].mechanism, "reliable_stream_broker_checkpoint_cursor")
        self.assertEqual(by_id["HG-SOL62-224"].mechanism, "framework_agnostic_agent_runtime_binding")



if __name__ == "__main__":
    unittest.main()
