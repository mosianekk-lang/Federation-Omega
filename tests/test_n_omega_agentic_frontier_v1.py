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
        self.assertEqual(s["vendor_reference_count"], 22)
        self.assertEqual(s["capability_gene_count"], 63)
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
        self.assertEqual(len(ids), 63)
        self.assertEqual(len(ids), len(set(ids)))
        for gene in c.genes.values():
            self.assertTrue(gene.sources)
            self.assertTrue(gene.binding)
            self.assertTrue(gene.proof_gate)


    def test_2026_frontier_residuals_auto_adopt(self):
        p = AgenticFrontierCompiler().compile(MissionProfile(
            mission_id="F2026",
            domains=frozenset({"ORCHESTRATION", "TOOLS", "EXECUTION", "MEMORY", "EVALUATION"}),
            long_running=True,
            multi_agent=True,
            tool_heavy=True,
            browser_or_computer=True,
            requires_dynamic_models=True,
            requires_release=True,
            requires_artifact_production=True,
            requires_local_multimodal=True,
        ))
        for gene in (
            "AGF-041","AGF-042","AGF-043","AGF-044","AGF-045","AGF-046",
            "AGF-047","AGF-048","AGF-049","AGF-050","AGF-051","AGF-052","AGF-053"
        ):
            self.assertIn(gene, p.selected_gene_ids)
        self.assertIn("PROVIDER_IDENTITY", p.proof_required)
        self.assertIn("SEMANTIC_PROVIDER_READBACK", p.proof_required)

    def test_clean_room_summary_boundary(self):
        s = frontier_summary()
        self.assertTrue(s["clean_room_harvest"])
        self.assertFalse(s["proprietary_weights_imported"])
        self.assertFalse(s["undocumented_vendor_internals_imported"])
        self.assertEqual(len(s["frontier_2026_gene_ids"]), 23)

    def test_explicit_residual_flags_select_without_broad_domains(self):
        p = AgenticFrontierCompiler().compile(MissionProfile(
            mission_id="R",
            domains=frozenset({"SPECIFICATION"}),
            requires_adaptive_effort=True,
            requires_cross_window_context=True,
            requires_dynamic_tools=True,
            requires_portable_skills=True,
            requires_persistent_agent=True,
            requires_adaptive_computer_use=True,
            requires_hypothesis_evolution=True,
            requires_strict_self_verification=True,
            requires_harness_simplification=True,
            requires_artifact_production=True,
            requires_local_multimodal=True,
        ))
        for gene in [f"AGF-{i:03d}" for i in range(41,54)]:
            self.assertIn(gene, p.selected_gene_ids)


    def test_external_frontier_residuals_054_063_auto_adopt(self):
        p = AgenticFrontierCompiler().compile(MissionProfile(
            mission_id="EXT2026",
            domains=frozenset({"DURABILITY", "TOOLS", "ORCHESTRATION", "EXECUTION", "ROUTING", "SECURITY"}),
            long_running=True,
            tool_heavy=True,
            code_execution=True,
            browser_or_computer=True,
            consequential=True,
            requires_release=True,
            requires_persistent_agent=True,
            requires_local_multimodal=True,
        ))
        for gene in [f"AGF-{i:03d}" for i in range(54,64)]:
            self.assertIn(gene, p.selected_gene_ids)
        self.assertIn("ACTION_SPECIFIC_AUTHORITY", p.proof_required)
        self.assertIn("POST_EFFECT_READBACK", p.proof_required)

    def test_external_frontier_residual_flags_select_individually(self):
        p = AgenticFrontierCompiler().compile(MissionProfile(
            mission_id="EXTFLAGS",
            domains=frozenset({"SPECIFICATION"}),
            requires_async_job_handle=True,
            requires_exact_resume=True,
            requires_tool_catalog_cache=True,
            requires_async_task_delivery=True,
            requires_browser_offscreen_liveness=True,
            requires_replay_safe_versioning=True,
            requires_adaptive_worker_capacity=True,
            requires_local_openai_compat=True,
            requires_failure_domain_spread=True,
            requires_oauth_mixup_hardening=True,
        ))
        for gene in [f"AGF-{i:03d}" for i in range(54,64)]:
            self.assertIn(gene, p.selected_gene_ids)



if __name__ == "__main__":
    unittest.main()
