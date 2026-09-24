from __future__ import annotations

import unittest

from services.sol62_client_runtime.asia_frontier_p1_p2 import (
    ContextItem,
    DeploymentCell,
    DeviceCarrier,
    ModelRoute,
    ReasoningMode,
    RegionalModelResult,
    ResearchHypothesis,
    ResearchResult,
    RuntimeCell,
    Specialist,
    compile_cross_device_takeover,
    compile_cross_system_automation,
    compile_deep_retrieval_plan,
    compile_engineering_loop,
    compile_p1_p2_plan,
    compile_private_enterprise_dev_plane,
    evaluate_regional_models,
    externalize_working_set,
    hybrid_reasoning_route,
    multimodal_surface_contract,
    plan_first_alignment,
    recursive_research_cycle,
    select_compact_private_multimodal,
    select_efficient_model_route,
    select_reasoning_effort,
    select_sovereign_deployment,
    synthesize_specialist_collective,
    terminal_coding_loop_state,
    typed_code_runtime_adapter,
)


class Sol62AsiaFrontierP1P2Tests(unittest.TestCase):
    def test_externalized_context_preserves_immutable_and_contradiction_priority(self):
        result = externalize_working_set(
            (
                ContextItem("owner", "owner constraint", 20, 0.9, 1.0, immutable=True),
                ContextItem("contradiction", "conflict", 20, 0.8, 0.9, contradiction_risk=0.95),
                ContextItem("low", "background", 40, 0.1, 0.2),
            ),
            active_token_budget=45,
        )
        self.assertEqual(result["state"], "READY")
        self.assertIn("owner", result["active_item_ids"])
        self.assertIn("contradiction", result["contradiction_item_ids"])
        self.assertIn("low", result["externalized_item_ids"])

    def test_reasoning_effort_scales_with_risk_and_uncertainty(self):
        deep = select_reasoning_effort(
            risk=0.95, uncertainty=0.9, reversibility=0.1, cost_pressure=0.2
        )
        self.assertEqual(deep["mode"], ReasoningMode.DEEP.value)
        fast = select_reasoning_effort(
            risk=0.05, uncertainty=0.05, reversibility=1.0, cost_pressure=1.0, deadline_pressure=1.0
        )
        self.assertEqual(fast["mode"], ReasoningMode.FAST.value)
        self.assertFalse(deep["authority_granted"])

    def test_engineering_loop_is_end_to_end_but_not_source_authority(self):
        result = compile_engineering_loop(
            requirement="fix a repository defect",
            repo_epoch="abc123",
            tests_available=True,
            acceptance_predicates=("tests pass", "semantic readback"),
        )
        self.assertEqual(result["state"], "READY")
        self.assertIn("DEBUG_FAILURES", result["phases"])
        self.assertIn("INDEPENDENT_REVIEW", result["phases"])
        self.assertFalse(result["source_mutation_authority_granted"])

    def test_terminal_coding_loop_requires_all_local_predicates(self):
        result = terminal_coding_loop_state(
            compile_pass=True,
            targeted_tests_pass=True,
            regression_tests_pass=False,
            semantic_readback_pass=True,
            unresolved_failures=0,
        )
        self.assertEqual(result["next_action"], "REPAIR_REGRESSION")
        ready = terminal_coding_loop_state(
            compile_pass=True,
            targeted_tests_pass=True,
            regression_tests_pass=True,
            semantic_readback_pass=True,
            unresolved_failures=0,
        )
        self.assertEqual(ready["next_action"], "READY_FOR_PROOFOS")
        self.assertFalse(ready["source_admitted"])

    def test_deep_retrieval_respects_privacy_and_provenance(self):
        result = compile_deep_retrieval_plan(
            query="find current evidence",
            allowed_surfaces=("WEB", "MCP", "FILES", "KDV"),
            privacy_class="SECRET",
        )
        self.assertEqual(result["state"], "READY")
        self.assertNotIn("WEB", result["surfaces"])
        self.assertNotIn("MCP", result["surfaces"])
        self.assertTrue(result["source_provenance_required"])

    def test_hybrid_reasoning_never_commits_fast_effect(self):
        result = hybrid_reasoning_route(
            task_complexity=0.9,
            uncertainty=0.8,
            failure_cost=0.9,
            observed_fast_confidence=0.2,
        )
        self.assertEqual(result["escalate_to"], "DEEP")
        self.assertFalse(result["fast_result_may_commit_effect"])

    def test_model_efficiency_hard_gates_context_modalities_and_privacy(self):
        routes = (
            ModelRoute("local", ("GENERATE",), 100000, ("text", "image"), True, 1.0, 0.9, 0.2, 500, 0.2),
            ModelRoute("remote", ("GENERATE",), 1000000, ("text", "image"), False, 0.4, 0.99, 0.05, 200, 0.1),
        )
        result = select_efficient_model_route(
            routes,
            required_role="generate",
            required_context=50000,
            required_modalities=("image",),
            minimum_privacy=0.9,
        )
        self.assertEqual(result["selected_route_id"], "local")
        self.assertFalse(result["provider_call_authority_granted"])

    def test_collective_intelligence_is_bounded_by_specialist_capacity(self):
        result = synthesize_specialist_collective(
            (("t1", "CODE"), ("t2", "CODE"), ("t3", "RESEARCH")),
            (
                Specialist("coder", ("CODE",), "INTERNAL", 1),
                Specialist("researcher", ("RESEARCH",), "INTERNAL", 1),
            ),
        )
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(len(result["unassigned_task_ids"]), 1)
        self.assertFalse(result["authority_granted"])

    def test_recursive_research_tracks_falsification_and_never_self_authorizes(self):
        result = recursive_research_cycle(
            (
                ResearchHypothesis("h1", "a", "not a", 0.9),
                ResearchHypothesis("h2", "b", "not b", 0.8),
                ResearchHypothesis("h3", "c", "not c", 0.7),
            ),
            (
                ResearchResult("h1", True, 0.9, True),
                ResearchResult("h2", False, 0.9, True),
            ),
        )
        self.assertIn("h1", result["falsified_hypothesis_ids"])
        self.assertIn("h2", result["accepted_hypothesis_ids"])
        self.assertIn("h3", result["next_hypothesis_ids"])
        self.assertFalse(result["self_modification_authority_granted"])

    def test_cross_system_automation_is_plan_not_effect(self):
        result = compile_cross_system_automation(
            intent="collect and reconcile project state",
            systems=("GITHUB", "DRIVE", "M365"),
            data_classes={"GITHUB": "PUBLIC", "DRIVE": "PRIVATE", "M365": "PRIVATE"},
        )
        self.assertEqual(result["state"], "READY")
        self.assertEqual(len(result["steps"]), 3)
        self.assertFalse(result["effect_authority_granted"])
        self.assertTrue(all(row["semantic_readback_required"] for row in result["steps"]))

    def test_compact_private_multimodal_requires_local_privacy_fit(self):
        routes = (
            ModelRoute("local-mm", ("VISION",), 32000, ("text", "image", "document"), True, 1.0, 0.88, 0.2, 800, 0.3),
            ModelRoute("cloud-mm", ("VISION",), 1000000, ("text", "image", "document"), False, 0.5, 0.99, 0.1, 300, 0.1),
        )
        result = select_compact_private_multimodal(
            routes, max_cost=1.0, minimum_privacy=0.9, modalities=("image", "document")
        )
        self.assertEqual(result["selected_route_id"], "local-mm")

    def test_cross_device_takeover_preserves_mission_and_requires_effect_readback(self):
        result = compile_cross_device_takeover(
            mission_id="m1",
            current_carrier_id="chat",
            current_carrier_epoch=7,
            candidates=(
                DeviceCarrier("chat", "browser", 7, False, 0.7, ("CHAT",)),
                DeviceCarrier("fuse", "fuse-native", 4, True, 1.0, ("CHAT", "WORKSPACE")),
            ),
            inflight_effect_ids=("effect-1",),
        )
        self.assertEqual(result["state"], "READBACK_REQUIRED")
        self.assertEqual(result["replacement_carrier_id"], "fuse")
        self.assertEqual(result["new_mission_carrier_epoch"], 8)
        self.assertTrue(result["effect_readback_before_takeover_commit"])

    def test_omnimodal_contract_separates_perception_from_gui_effect(self):
        result = multimodal_surface_contract(
            modalities=("text", "image", "audio", "video"), gui_actions_required=True
        )
        self.assertEqual(result["state"], "READY")
        self.assertIn("gui", result["modalities"])
        self.assertFalse(result["gui_effect_authority_granted"])
        self.assertTrue(result["perception_ne_effect"])

    def test_private_enterprise_plane_requires_role_coverage(self):
        routes = (
            ModelRoute("coder", ("CODE",), 100000, ("text",), True, 1.0, 0.9, 0.2, 500),
            ModelRoute("reviewer", ("REVIEW",), 100000, ("text",), True, 1.0, 0.9, 0.2, 500),
        )
        result = compile_private_enterprise_dev_plane(
            routes, required_roles=("CODE", "REVIEW"), minimum_privacy=0.9
        )
        self.assertEqual(result["state"], "READY")
        self.assertFalse(result["provider_call_authority_granted"])

    def test_plan_first_alignment_holds_ambiguity(self):
        result = plan_first_alignment(
            objective="deploy feature",
            constraints=("no downtime",),
            acceptance_predicates=("health passes",),
            ambiguities=("which tenant?",),
        )
        self.assertEqual(result["state"], "HOLD")
        self.assertFalse(result["execution_allowed"])

    def test_typed_code_runtime_seam_hard_gates_resources_and_network(self):
        cell = RuntimeCell("local", ("PYTHON",), False, "READ_WRITE_WORKSPACE", 2.0, 1024)
        denied = typed_code_runtime_adapter(
            operation="PYTHON",
            cell=cell,
            requested_network=True,
            requested_filesystem_mode="READ_WRITE_WORKSPACE",
            cpu=1.0,
            memory_mb=512,
        )
        self.assertEqual(denied["reason"], "NETWORK_NOT_ALLOWED")
        ready = typed_code_runtime_adapter(
            operation="PYTHON",
            cell=cell,
            requested_network=False,
            requested_filesystem_mode="READ_WRITE_WORKSPACE",
            cpu=1.0,
            memory_mb=512,
        )
        self.assertEqual(ready["state"], "READY")
        self.assertFalse(ready["effect_authority_granted"])

    def test_sovereign_deployment_requires_data_ops_technology_and_exit(self):
        result = select_sovereign_deployment(
            (
                DeploymentCell("a", "ZA", "ZA", "OWNER", True, True, True),
                DeploymentCell("b", "ZA", "EU", "VENDOR", True, False, True),
            ),
            required_data_residency="ZA",
            required_operations_residency="ZA",
            required_technology_control="OWNER",
        )
        self.assertEqual(result["selected_cell_id"], "a")
        self.assertFalse(result["deployment_authority_granted"])

    def test_regional_model_eval_is_measured_not_market_superiority(self):
        result = evaluate_regional_models(
            (
                RegionalModelResult("jp-a", "ja", 12, 0.9, 0.85, 0.92, 0.95, 500, 0.2),
                RegionalModelResult("jp-b", "ja", 12, 0.88, 0.9, 0.85, 0.96, 400, 0.1),
            ),
            language="ja",
        )
        self.assertEqual(result["state"], "MEASURED")
        self.assertFalse(result["market_superiority_proven"])

    def test_p1_p2_plan_covers_all_remaining_18_genes(self):
        plan = compile_p1_p2_plan(
            objective="build private multimodal software engineering and research runtime",
            reason="Asia frontier convergence",
        )
        self.assertEqual(plan["state"], "P1_P2_RUNTIME_MECHANISMS_AVAILABLE")
        self.assertEqual(plan["p1_count"], 11)
        self.assertEqual(plan["p2_count"], 7)
        ids = {row["gene_id"] for row in plan["p1"] + plan["p2"]}
        self.assertEqual(len(ids), 18)
        self.assertFalse(plan["source_mutation_authority_granted"])
        self.assertFalse(plan["provider_effect_authority_granted"])
        self.assertFalse(plan["market_superiority_proven"])


if __name__ == "__main__":
    unittest.main()
