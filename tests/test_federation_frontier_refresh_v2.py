import unittest

from benchmarking.cfbe_omega.federation_frontier_refresh_v2 import (
    FRONTIER_EVIDENCE,
    FrontierState,
    WorkLane,
    SandboxState,
    agent_optimizer_gate,
    agent_telemetry_gate,
    ai_asset_inventory_gate,
    benchmark_20_dimension_summary,
    compile_frontier_genome_receipt,
    durable_lane_plan,
    evaluation_campaign_plan,
    hook_execution_policy,
    idempotency_v2_contract,
    sandbox_execution_plan,
    supply_chain_v12_gate,
    toolbox_governance_plan,
    validate_frontier_evidence,
)


class FederationFrontierRefreshV2Tests(unittest.TestCase):
    def test_frontier_evidence_is_public_official_and_authority_neutral(self):
        validate_frontier_evidence()
        self.assertGreaterEqual(len(FRONTIER_EVIDENCE), 15)
        self.assertTrue(all(not item.grants_authority for item in FRONTIER_EVIDENCE))

    def test_hyperleverage_100_remains_exactly_routed(self):
        receipt = compile_frontier_genome_receipt()
        self.assertEqual(100, receipt.gene_count)
        self.assertEqual(100, receipt.routed_count)
        self.assertEqual((), receipt.unrouted_gene_ids)
        self.assertGreaterEqual(receipt.strengthened_v2_count, 20)
        self.assertEqual(2, receipt.provider_gated_count)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_allowed)
        by_id = {item.gene_id: item for item in receipt.audits}
        self.assertEqual(FrontierState.STRENGTHENED_SOURCE_V2, by_id["FHU-090"].state)
        self.assertEqual(FrontierState.PROVIDER_GATED, by_id["FHU-042"].state)

    def test_long_waiting_work_uses_durable_lane_only_when_resumable_runtime_exists(self):
        held = durable_lane_plan(expected_runtime_seconds=90, waits_for_external_event=True)
        self.assertEqual(WorkLane.HOLD, held.lane)
        self.assertIn("resumable_runtime_provider_open", held.reasons)
        ready = durable_lane_plan(expected_runtime_seconds=90, waits_for_external_event=True, resumable_runtime_available=True)
        self.assertEqual(WorkLane.DURABLE_WORKFLOW, ready.lane)
        self.assertTrue(ready.provider_runtime_proven)

    def test_sandbox_is_fail_closed_for_effects_without_exact_permit(self):
        held = sandbox_execution_plan(requires_code_execution=True, isolated_workspace_available=True, resumable_session_available=True, effectful=True, exact_effect_permit=False)
        self.assertEqual(SandboxState.HOLD_EFFECT_AUTHORITY, held.state)
        self.assertFalse(held.provider_effect_authorized)

    def test_toolbox_requires_registry_auth_and_pinned_versions(self):
        held = toolbox_governance_plan({"mcp-drive": "latest", "proofos": "1.2.3"}, centralized_registry=False, centralized_auth=True)
        self.assertEqual("HOLD_TOOLBOX_GOVERNANCE", held.state)
        self.assertIn("centralized_registry", held.missing)
        self.assertTrue(any(item.startswith("version_pinning:") for item in held.missing))

    def test_eval_campaign_demands_golden_real_failure_and_sample_coverage(self):
        plan = evaluation_campaign_plan(golden_cases=0, production_failure_cases=0, synthetic_cases=3)
        self.assertEqual("EVAL_CAMPAIGN_FORMATION_REQUIRED", plan.state)
        self.assertEqual(("add_golden_semantic_cases", "harvest_real_failure_clusters", "synthesize_additional_cases"), plan.required_next_actions)

    def test_optimizer_never_self_promotes_stable_state(self):
        decision = agent_optimizer_gate(baseline_score=0.71, candidate_score=0.82, paired_cases=30, hard_regressions=0, owner_value_observed=True, provider_runtime_proven=True)
        self.assertEqual("CANDIDATE_PROMOTION_REVIEW", decision.state)
        self.assertFalse(decision.stable_promotion_allowed)

    def test_ai_asset_inventory_requires_owner_lineage_risk_value_and_proof(self):
        receipt = ai_asset_inventory_gate([
            {"asset_id": "agent-1", "asset_type": "agent", "owner": "Bubbles", "lineage": "main", "risk_state": "LOW", "value_state": "MEASURED", "proof_ref": "r1"},
            {"asset_id": "mcp-1", "asset_type": "mcp", "owner": "Bridge", "lineage": "main", "risk_state": "UNKNOWN", "value_state": "", "proof_ref": "r2"},
        ])
        self.assertEqual("AI_ASSET_INVENTORY_GAPS", receipt.state)
        self.assertEqual(("mcp-1",), receipt.incomplete_asset_ids)

    def test_agent_telemetry_requires_agent_tool_guardrail_handoff_cost_and_resource_fields(self):
        fields = {"mission.trace_id", "agent.id", "agent.turn", "tool.name", "tool.result_state", "guardrail.state", "handoff.target", "latency_ms", "token.input", "token.output", "error.type", "memory.operation", "gateway.operation"}
        receipt = agent_telemetry_gate(fields)
        self.assertEqual("AGENT_TELEMETRY_READY", receipt.state)
        self.assertEqual((), receipt.missing_fields)
        self.assertEqual("1.44.0", receipt.semantic_convention_version)

    def test_slsa_12_stable_requires_source_build_hosted_and_attestation(self):
        held = supply_chain_v12_gate(release_class="stable", source_provenance=True, build_provenance=True, hosted_build=True, artifact_attestation=False)
        self.assertEqual("HOLD_SUPPLY_CHAIN_V12", held.state)
        self.assertEqual(("artifact_attestation",), held.missing)

    def test_stripe_v2_style_idempotency_binds_method_scope_window_and_parameters(self):
        ready = idempotency_v2_contract(method="DELETE", key="k1", endpoint="/v2/example/123", account_scope="acct-1", age_days=5, parameters_match=True)
        self.assertEqual("IDEMPOTENT_REPLAY_ELIGIBLE", ready.state)
        self.assertTrue(ready.replay_eligible)
        mismatch = idempotency_v2_contract(method="POST", key="k1", endpoint="/v2/example", account_scope="acct-1", age_days=5, parameters_match=False)
        self.assertEqual("REJECT_PARAMETER_MISMATCH", mismatch.state)

    def test_hooks_require_trust_review_and_effect_permit(self):
        rejected = hook_execution_policy(trusted_source=False, reviewed=True, sandboxed=True, effectful=False, exact_effect_permit=False)
        self.assertEqual("REJECT_UNTRUSTED_HOOK", rejected.state)
        effect_hold = hook_execution_policy(trusted_source=True, reviewed=True, sandboxed=True, effectful=True, exact_effect_permit=False)
        self.assertEqual("HOLD_EFFECT_PERMIT_REQUIRED", effect_hold.state)

    def test_full_cfbe_snapshot_restores_twenty_dimensions(self):
        summary = benchmark_20_dimension_summary()
        self.assertEqual(20, summary["dimension_count"])
        self.assertEqual(85.9, summary["raw_architecture_average"])
        self.assertEqual(67.45, summary["proof_adjusted_average"])
        self.assertIn("AI infrastructure/edge/physical AI", summary["lowest_proof_dimensions"])
        self.assertIn("Governance/provenance/auditability", summary["highest_proof_dimensions"])
        self.assertFalse(summary["vendor_certified"])


if __name__ == "__main__":
    unittest.main()
