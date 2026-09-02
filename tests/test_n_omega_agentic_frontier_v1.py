import unittest

from benchmarking.cfbe_omega.n_omega_agentic_frontier_v1 import (
    AgenticFrontierCompiler,
    MissionProfile,
    compile_n_directive,
    frontier_summary,
)


class NOmegaAgenticFrontierTests(unittest.TestCase):
    def test_frontier_coverage_and_truth_boundary(self):
        s = frontier_summary()
        self.assertEqual(s["vendor_reference_count"], 17)
        self.assertEqual(s["capability_gene_count"], 40)
        self.assertEqual(s["domain_count"], 18)
        self.assertTrue(s["zero_unrouted"])
        self.assertTrue(s["one_mutating_lane"])
        self.assertFalse(s["stable_self_promotion_authorized"])
        self.assertFalse(s["provider_effect_authorized_by_benchmark"])
        self.assertTrue(s["n_omega_cfbe_integrated"])

    def test_consequential_multiagent_compiles_proof_safe_superstack(self):
        p = AgenticFrontierCompiler().compile(MissionProfile(
            mission_id="T",
            domains=frozenset({"ORCHESTRATION", "TOOLS", "SECURITY"}),
            long_running=True,
            multi_agent=True,
            tool_heavy=True,
            consequential=True,
            requires_memory=True,
            requires_dynamic_models=True,
            requires_release=True,
        ))
        self.assertEqual(p.max_mutating_lanes, 1)
        self.assertEqual(p.external_model_authority, "PROPOSAL_ONLY")
        self.assertIn("AGF-034", p.selected_gene_ids)
        self.assertIn("AGF-035", p.selected_gene_ids)
        self.assertIn("ACTION_SPECIFIC_AUTHORITY", p.proof_required)
        self.assertIn("POST_EFFECT_READBACK", p.proof_required)
        self.assertIn("DURABLE_CHECKPOINT_RESUME", p.orchestration)
        self.assertIn("INDEPENDENT_CHALLENGER", p.orchestration)

    def test_provider_gated_requires_native_readback(self):
        p = AgenticFrontierCompiler().compile(MissionProfile(
            mission_id="P",
            domains=frozenset({"EXECUTION"}),
            browser_or_computer=True,
        ))
        self.assertIn("PROVIDER_IDENTITY", p.proof_required)
        self.assertIn("SEMANTIC_PROVIDER_READBACK", p.proof_required)

    def test_n_omega_cfbe_bridge_is_integrated_but_independent(self):
        p = compile_n_directive(MissionProfile(
            mission_id="N",
            domains=frozenset({"ORCHESTRATION", "EVALUATION"}),
            multi_agent=True,
        ))
        self.assertEqual(p.lifecycle[0], "CFBE_PREPASS")
        self.assertIn("N_COMPILE", p.lifecycle)
        self.assertEqual(p.lifecycle[-2], "CFBE_POSTPASS")
        self.assertEqual(p.cfbe_role, "INDEPENDENT_BENCHMARK_CHALLENGE_EVOLUTION_GOVERNOR")
        self.assertEqual(p.n_omega_role, "MISSION_COMPILER_EXECUTION_MANAGER")
        self.assertFalse(p.self_certification_allowed)
        self.assertTrue(p.stable_promotion_requires_owner_value)

    def test_compiler_catalog_unique_and_complete(self):
        c = AgenticFrontierCompiler()
        c.validate()
        ids = list(c.genes)
        self.assertEqual(len(ids), 40)
        self.assertEqual(len(ids), len(set(ids)))
        for gene in c.genes.values():
            self.assertTrue(gene.sources)
            self.assertTrue(gene.binding)
            self.assertTrue(gene.proof_gate)


if __name__ == "__main__":
    unittest.main()
