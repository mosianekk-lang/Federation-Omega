from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NDirectiveV3ContractTests(unittest.TestCase):
    def test_n_v3_preserves_authority_and_adds_parallel_prompt_fabric(self):
        text = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        required = (
            "policy_id: FEDOMEGA-N-DIRECTIVE-V3",
            "version: 3.5.0",
            "authority_ceiling: A1_INTERNAL",
            "external_effect_default: false",
            "compile unfinished work into a finite dependency DAG",
            "execute the maximum useful parallelism for effect-free independent work",
            "must_serialize:",
            "provider mutations",
            "repeated_fingerprint_threshold: 2",
            "MATERIALLY_DIFFERENT_ROUTE_REQUIRED",
            "evaluate prompt friction with the CFBE Prompt Scientist",
            "critical regression",
            "PRODUCTION_VERIFIED",
            "ten_x_is_a_measured_target_not_a_prompt_claim: true",
        )
        for marker in required:
            self.assertIn(marker, text)

    def test_blocker_containment_prevents_single_lane_global_stall(self):
        text = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        for required in (
            "policy_id: FUSE-BLOCKER-CONTAINMENT-V1",
            "GLOBAL_STALL requires empty READY set plus universal causal dependency",
            "work-steal all disjoint READY nodes",
            "disjoint branch preparation, build, tests and PR proof",
            "fdof_v3_scoped_registry_is_target_for_disjoint_concurrent_admission: true",
        ):
            self.assertIn(required, text)

        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        self.assertEqual(bootstrap["version"], "3.5.0")
        self.assertTrue(bootstrap["parallelism"]["blocker_scope_locality_required"])
        self.assertTrue(bootstrap["parallelism"]["global_stall_requires_empty_ready_set_and_universal_causal_dependency"])
        self.assertTrue(bootstrap["parallelism"]["branch_prepare_build_test_pr_may_continue_while_main_admission_is_held"])
        self.assertEqual(bootstrap["blocker_containment"]["failure_class"], "CFAIL-20260919-029")
        self.assertEqual(bootstrap["source_concurrency"]["v3_registry_ref"], "refs/heads/locks/fdof-v3-scoped-registry")

        finality = (ROOT / "governance/FUSE_ALPHA_OMEGA_FORMATION_60_MIN_FINALITY_PROMPT_V1.md").read_text()
        self.assertIn("BLOCKER CONTAINMENT / ANTI-HEAD-OF-LINE INVARIANT", finality)
        self.assertIn("GLOBAL_STALL", finality)
        self.assertIn("Disjoint branch preparation", finality)

    def test_chat_capacity_and_bible_fleet_are_bound_without_global_stall(self):
        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        self.assertFalse(bootstrap["chat_capacity_continuity"]["owner_click_copy_paste_required"])
        self.assertTrue(bootstrap["bible_fleet_completion"]["future_registered_owning_bibles_auto_inherit"])
        self.assertEqual(bootstrap["bible_fleet_completion"]["semantic_dedupe"], "JOIN_REUSE_EXISTING_WORKPLANE_MISSION_BUS_FDOF")

        directive = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        self.assertIn("chat_capacity_continuity:", directive)
        self.assertIn("bible_fleet_completion:", directive)
        self.assertIn("future_owning_bibles_auto_inherit: true", directive)

        prompt = (ROOT / "governance/FUSE_ALPHA_OMEGA_FORMATION_60_MIN_FINALITY_PROMPT_V1.md").read_text()
        self.assertIn("CHAT-CAPACITY CONTINUITY", prompt)
        self.assertIn("FEDERATION BIBLE FLEET COMPLETION", prompt)

    def test_transport_interruption_is_effect_safe_and_never_global_stall(self):
        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        transport = bootstrap["chat_transport_continuity"]
        self.assertEqual(transport["classifier"], "TRANSPORT_INTERRUPTION")
        self.assertTrue(transport["no_response_ne_no_effect"])
        self.assertFalse(transport["owner_action_required_while_safe_route_exists"])
        self.assertIn("freeze blind replay of any action whose effect state is unknown", transport["mandatory_sequence"])
        self.assertIn("read back FDOF/effect/provider/mission receipts for any possibly in-flight tool or external action", transport["mandatory_sequence"])

        directive = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        self.assertIn("chat_transport_continuity:", directive)
        self.assertIn("no_response_ne_no_effect: true", directive)
        self.assertIn("work-steal all disjoint READY work", directive)

        prompt = (ROOT / "governance/FUSE_ALPHA_OMEGA_FORMATION_60_MIN_FINALITY_PROMPT_V1.md").read_text()
        self.assertIn("CHAT TRANSPORT INTERRUPTION CONTINUITY", prompt)
        self.assertIn("NO_RESPONSE != NO_EFFECT", prompt)
        self.assertIn("Connection interrupted. Waiting for the complete answer", prompt)

    def test_chat_failure_matrix_preserves_user_stop_and_cross_tab_fencing(self):
        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        matrix = bootstrap["chat_failure_continuity_matrix"]
        self.assertIn("USER_INTERRUPTION", matrix["classes"])
        self.assertEqual(matrix["classes"]["USER_INTERRUPTION"]["effect_rule"], "EXPLICIT_USER_STOP_OR_CANCEL_IS_AUTHORITATIVE_FOR_THAT_INTENT")
        self.assertTrue(matrix["cross_tab_takeover"]["mission_client_epoch_required"])
        self.assertTrue(matrix["cross_tab_takeover"]["stale_client_auto_send_forbidden"])
        self.assertEqual(matrix["partial_response"]["visible_tool_call_without_terminal_answer_state"], "POSSIBLE_EFFECT_PENDING_READBACK")
        self.assertTrue(matrix["partial_response"]["partial_text_is_not_terminal_proof"])

        directive = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        self.assertIn("chat_failure_continuity_matrix:", directive)
        self.assertIn("stale_client_auto_send_forbidden: true", directive)
        self.assertIn("explicit owner stop/cancel is authoritative", directive)

        prompt = (ROOT / "governance/FUSE_ALPHA_OMEGA_FORMATION_60_MIN_FINALITY_PROMPT_V1.md").read_text()
        self.assertIn("CHAT/CLIENT FAILURE CONTINUITY MATRIX", prompt)
        self.assertIn("Cross-tab writer fencing", prompt)
        self.assertIn("PARTIAL_UNACKED", prompt)

    def test_client_liveness_supervisor_handles_silent_stall_without_false_takeover(self):
        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        live = bootstrap["client_liveness_supervisor"]
        self.assertTrue(live["stall_detection"]["pure_elapsed_time_is_not_terminal_failure"])
        self.assertTrue(live["stall_detection"]["confirmed_stall_requires_independent_supporting_signal_or_hard_runtime_policy_boundary"])
        self.assertTrue(live["takeover"]["expiry_ne_release"])
        self.assertTrue(live["takeover"]["current_epoch_cas_required"])
        self.assertTrue(live["takeover"]["possible_effect_readback_required_before_new_writer_commit"])
        self.assertEqual(live["orphan_detection"]["interrupted_tool_marker_without_result"], "POSSIBLE_EFFECT_PENDING_READBACK")
        self.assertEqual(live["orphan_detection"]["late_terminal_after_takeover"], "STALE_EPOCH_RECONCILE_ONLY")

        directive = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        self.assertIn("client_liveness_supervisor:", directive)
        self.assertIn("banner_required_for_detection: false", directive)
        self.assertIn("stale_heartbeat_ne_release: true", directive)

        prompt = (ROOT / "governance/FUSE_ALPHA_OMEGA_FORMATION_60_MIN_FINALITY_PROMPT_V1.md").read_text()
        self.assertIn("CLIENT LIVENESS SUPERVISOR / SILENT FAILURE", prompt)
        self.assertIn("SUSPECT_NO_PROGRESS", prompt)
        self.assertIn("RESULT_PRESENT_RESPONSE_ORPHANED", prompt)

    def test_compiler_contract_is_safe_by_default(self):
        contract = json.loads((ROOT / "governance/cfbe_parallel_mission_compiler_v4.json").read_text())
        self.assertEqual(contract["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(contract["external_effect_default"])
        self.assertTrue(contract["composition"]["does_not_create_second_sovereign_scheduler"])
        self.assertFalse(contract["truth_boundary"]["stored_source_proves_runtime"])
        self.assertEqual(contract["failure_recovery"]["same_fingerprint_threshold"], 2)

    def test_architecture_contract_records_v3_composition_without_global_instruction_dependency(self):
        text = (ROOT / "docs/architecture/CFBE_PARALLEL_PROMPT_FABRIC_V4.md").read_text()
        self.assertIn("CFBE Parallel Prompt Fabric v4", text)
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V3", text)
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V2@2.1.0", text)
        self.assertIn("rollback/historical compatibility", text)
        self.assertIn("Prompt Scientist", text)
        self.assertIn("PRODUCTION_VERIFIED", text)
        self.assertIn("10x", text)

    def test_node_bootstrap_v3_composes_v2_and_requires_v3_engines(self):
        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        self.assertTrue(bootstrap["predecessor_must_pass"])
        self.assertEqual(bootstrap["predecessor_bootstrap"], "governance/federation_node_bootstrap_v2.json")
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V2", bootstrap["inherited_policies"])
        self.assertIn("FEDOMEGA-N-DIRECTIVE-V3", bootstrap["inherited_policies"])
        self.assertIn("CFBE-PARALLEL-MISSION-COMPILER-V4", bootstrap["inherited_policies"])
        self.assertIn("CFBE-PROMPT-SCIENTIST-V1", bootstrap["inherited_policies"])
        self.assertFalse(bootstrap["authority"]["external_effect_default"])
        self.assertFalse(bootstrap["prompt_evolution"]["constitutional_invariants_mutable"])
        self.assertTrue(bootstrap["activation"]["requires_merged_main_readback"])
        self.assertTrue(bootstrap["activation"]["master_bible_reconciliation_required"])

    def test_prompt_scientist_contract_has_exact_100_point_score_and_absolute_veto(self):
        contract = json.loads((ROOT / "governance/cfbe_prompt_scientist_v1.json").read_text())
        self.assertEqual(sum(contract["score_weights"].values()), 100)
        self.assertTrue(contract["promotion"]["critical_regression_is_absolute_veto"])
        self.assertTrue(contract["promotion"]["rollback_to_incumbent_required"])
        self.assertFalse(contract["truth_boundary"]["autonomous_model_weight_retraining_claimed"])


    def test_frontier_capability_compiler_is_inherited_and_required(self):
        text = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        self.assertIn(
            "agentic_frontier_compiler: benchmarking/cfbe_omega/n_omega_agentic_frontier_v1.py",
            text,
        )
        self.assertIn("AGF-001..AGF-053", text)
        self.assertIn("AGF-041..AGF-053", text)
        self.assertIn("proprietary_weights_imported: false", text)
        self.assertIn("undocumented_vendor_internals_imported: false", text)

        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        self.assertEqual(
            bootstrap["required_contracts"]["frontier_compiler"],
            "benchmarking/cfbe_omega/n_omega_agentic_frontier_v1.py",
        )
        self.assertEqual(
            bootstrap["required_engines"]["agentic_frontier_compiler"],
            "REQUIRED_FOR_NONTRIVIAL_MISSIONS",
        )
        self.assertIn("COMPILE_FRONTIER_CAPABILITY_SUPERSTACK", bootstrap["required_sequence"])
        self.assertTrue(bootstrap["frontier_capability_adoption"]["automatically_select_by_mission_profile"])

        compiler = json.loads((ROOT / "governance/cfbe_parallel_mission_compiler_v4.json").read_text())
        self.assertTrue(compiler["composition"]["frontier_compile_required_before_packetization"])
        self.assertEqual(compiler["composition"]["frontier_gene_range"], "AGF-001..AGF-053")
        self.assertEqual(compiler["frontier_selection"]["external_model_authority"], "PROPOSAL_ONLY")


    def test_estate_resolution_portfolio_v2_and_more_v2_are_bootstrap_bound(self):
        bootstrap = json.loads((ROOT / "governance/federation_node_bootstrap_v3.json").read_text())
        self.assertEqual(bootstrap["version"], "3.5.0")
        self.assertEqual(bootstrap["estate_resolution"]["service_id"], "estate.resolve")
        self.assertFalse(bootstrap["estate_resolution"]["first_route_failure_is_estate_absence"])
        self.assertIn("BLK-90_AUTHORIZED_ROUTE_SPACE_EXHAUSTED", bootstrap["estate_resolution"]["blocker_states"])
        self.assertEqual(bootstrap["mission_route_portfolio_v2"]["score_id"], "PORTFOLIO_SCORE_V2")
        self.assertFalse(bootstrap["mission_route_portfolio_v2"]["route_name_diversity_is_failure_independence"])
        self.assertTrue(bootstrap["mission_route_portfolio_v2"]["portfolio_min_cut_required_for_critical_missions"])
        self.assertEqual(bootstrap["more_autonomous_convergence_v2"]["semantic_version"], "BOOTSTRAP_MORE_V2")
        self.assertFalse(bootstrap["more_autonomous_convergence_v2"]["wait_for_another_more_while_safe_ready_work_exists"])

        directive = (ROOT / "governance/federation_n_directive_v3.yaml").read_text()
        self.assertIn("estate_resolution:", directive)
        self.assertIn("mission_route_portfolio_v2:", directive)
        self.assertIn("score: PORTFOLIO_SCORE_V2", directive)
        self.assertIn("more_trigger:", directive)
        self.assertIn("semantic_version: BOOTSTRAP_MORE_V2", directive)

        prompt = (ROOT / "governance/FUSE_ALPHA_OMEGA_FORMATION_60_MIN_FINALITY_PROMPT_V1.md").read_text()
        self.assertIn("ESTATE RESOLUTION / CAPABILITY REALIZATION", prompt)
        self.assertIn("MISSION ROUTE PORTFOLIO V2", prompt)
        self.assertIn("MORE V2 AUTONOMOUS CONVERGENCE", prompt)
        self.assertIn("route-name diversity is not failure independence", prompt)



if __name__ == "__main__":
    unittest.main()
