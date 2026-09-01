from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.federation_competitive_upgrade_fabric_v1 import (
    ImplementationMode,
    ReleaseStage,
    RetryPolicy,
    benchmark_summary,
    compile_control_bindings,
    compile_competitive_profile,
    error_budget_assessment,
    evaluate_gene_control,
    executable_binding_summary,
    flake_classification,
    load_genome,
    operational_readiness_gate,
    orchestration_route,
    progressive_delivery_gate,
    retention_policy,
    supply_chain_gate,
)
from federation.mission_ir import MissionIR


def mission(**overrides) -> MissionIR:
    data = dict(
        mission_id="MISSION-COMPETITIVE-TEST",
        objective="Improve orchestration reliability and memory continuity",
        domain="FEDERATION",
        outcome_contract="Produce a verified competitive mission profile",
        source_frontier="CURRENT_VERIFIED_STATE",
        privacy_class="INTERNAL",
        rights_state="OWNER_CONTROLLED",
        effect_class="NO_EFFECT",
        owner_approval_required=False,
        rollback_required=False,
        proof_requirements=("proof",),
    )
    data.update(overrides)
    return MissionIR(**data)


class CompetitiveUpgradeFabricTests(unittest.TestCase):
    def test_genome_has_exactly_100_unique_complete_genes(self) -> None:
        genes = load_genome()
        self.assertEqual(len(genes), 100)
        self.assertEqual(len({g.gene_id for g in genes}), 100)
        self.assertEqual(genes[0].gene_id, "FHU-001")
        self.assertEqual(genes[-1].gene_id, "FHU-100")
        self.assertTrue(all(g.acceptance_gate for g in genes))

    def test_modes_are_truth_bounded(self) -> None:
        genes = load_genome()
        gated = [g for g in genes if g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT]
        self.assertGreaterEqual(len(gated), 1)
        self.assertTrue(all(g.wave == "W3" for g in gated))

    def test_all_100_genes_have_executable_fail_closed_bindings(self) -> None:
        bindings = compile_control_bindings()
        self.assertEqual(len(bindings), 100)
        self.assertEqual(len({item.gene_id for item in bindings}), 100)
        self.assertTrue(all(item.handler_name for item in bindings))
        self.assertEqual({item.handler_name for item in bindings}, {"require_reuse_proof", "require_composition_proof", "require_provider_native_proof"})
        summary = executable_binding_summary()
        self.assertEqual(summary["executable_binding_count"], 100)
        self.assertTrue(summary["all_fail_closed_without_proof"])
        self.assertFalse(summary["stable_promotion_allowed"])
        self.assertFalse(summary["provider_effect_authorized"])

    def test_catalog_mode_cannot_self_certify_implementation(self) -> None:
        decision = evaluate_gene_control("FHU-001")
        self.assertEqual(decision.state.value, "HOLD_MISSING_PROOF")
        self.assertEqual(set(decision.missing_evidence), {"source_binding", "test_proof", "owner_binding"})
        self.assertFalse(decision.runtime_proven)

    def test_composed_control_requires_proof_references_not_booleans(self) -> None:
        booleans = evaluate_gene_control("FHU-001", {"source_binding": True, "test_proof": True, "owner_binding": True})
        self.assertEqual(booleans.state.value, "HOLD_MISSING_PROOF")
        ready = evaluate_gene_control("FHU-001", {"source_binding": "source:module", "test_proof": "test:case", "owner_binding": "owner:MissionIR"})
        self.assertEqual(ready.state.value, "READY_FOR_INDEPENDENT_READBACK")
        self.assertFalse(ready.runtime_proven)
        self.assertFalse(ready.stable_promotion_allowed)

    def test_provider_gate_never_authorizes_effect_or_runtime(self) -> None:
        decision = evaluate_gene_control("FHU-042", {"provider_authority": "github:authority", "provider_readback": "github:attestation", "test_proof": "test:provider-gate"})
        self.assertEqual(decision.state.value, "READY_FOR_PROVIDER_REVIEW")
        self.assertFalse(decision.runtime_proven)
        self.assertFalse(decision.provider_effect_authorized)
        self.assertFalse(decision.stable_promotion_allowed)

    def test_unknown_gene_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "COMPETITIVE_GENE_UNKNOWN"):
            evaluate_gene_control("FHU-999")

    def test_benchmark_summary_never_self_promotes(self) -> None:
        summary = benchmark_summary()
        self.assertEqual(summary["gene_count"], 100)
        self.assertFalse(summary["stable_promotion_allowed"])
        self.assertFalse(summary["provider_effect_authorized"])
        self.assertLess(summary["proof_adjusted_operational_score"], summary["target_score"])

    def test_admission_router_direct_parallel_multi_agent_and_effect(self) -> None:
        item = mission()
        self.assertEqual(orchestration_route(item, dependency_count=1).value, "DIRECT")
        self.assertEqual(orchestration_route(item, dependency_count=4).value, "PARALLEL")
        self.assertEqual(orchestration_route(item, dependency_count=10).value, "MULTI_AGENT")
        effect = mission(effect_class="BOUNDED_EFFECT", authority_requirements=("exact-route-authority",), rollback_required=True)
        self.assertEqual(orchestration_route(effect, dependency_count=1).value, "EFFECT")

    def test_uncertainty_forces_adversarial_route(self) -> None:
        self.assertEqual(orchestration_route(mission(), uncertainty=0.9).value, "ADVERSARIAL")

    def test_error_budget_states(self) -> None:
        healthy = error_budget_assessment(total=100000, successful=99995, slo_target=0.999)
        self.assertEqual(healthy.state, "HEALTHY")
        exhausted = error_budget_assessment(total=1000, successful=990, slo_target=0.999)
        self.assertEqual(exhausted.state, "EXHAUSTED")

    def test_retry_policy_is_bounded_and_deterministic(self) -> None:
        policy = RetryPolicy(max_attempts=4, base_delay_ms=100, max_delay_ms=1000, idempotency_required=True)
        self.assertEqual(policy.delay_ms(2, "x"), policy.delay_ms(2, "x"))
        self.assertLessEqual(policy.delay_ms(4, "x"), 1000)

    def test_retention_keeps_sensitive_payloads_out_of_hot_memory(self) -> None:
        decision = retention_policy("HIGHLY_SENSITIVE", 1)
        self.assertFalse(decision.retain_payload)
        self.assertTrue(decision.retain_metadata)
        self.assertEqual(decision.tier, "COLD_POINTER_ONLY")

    def test_progressive_delivery_holds_on_regression(self) -> None:
        decision = progressive_delivery_gate(source_admitted=True, deterministic_tests_pass=True, shadow_pairs=30, hard_regressions=1, provider_readback=True, observed_owner_value=True)
        self.assertEqual(decision.stage, ReleaseStage.HOLD)

    def test_progressive_delivery_requires_observed_value_for_stable_review(self) -> None:
        canary = progressive_delivery_gate(source_admitted=True, deterministic_tests_pass=True, shadow_pairs=30, hard_regressions=0, provider_readback=True, observed_owner_value=False)
        self.assertEqual(canary.stage, ReleaseStage.CANARY)
        stable = progressive_delivery_gate(source_admitted=True, deterministic_tests_pass=True, shadow_pairs=30, hard_regressions=0, provider_readback=True, observed_owner_value=True)
        self.assertEqual(stable.stage, ReleaseStage.STABLE_REVIEW)

    def test_supply_chain_gate_requires_attestation_only_when_release_class_demands_it(self) -> None:
        ok, missing = supply_chain_gate(provenance=True, pinned_dependencies=True, sbom=True, artifact_attestation=False, release_requires_attestation=False)
        self.assertTrue(ok)
        self.assertEqual(missing, ())
        ok, missing = supply_chain_gate(provenance=True, pinned_dependencies=True, sbom=True, artifact_attestation=False, release_requires_attestation=True)
        self.assertFalse(ok)
        self.assertEqual(missing, ("artifact_attestation",))

    def test_operational_readiness_is_fail_closed(self) -> None:
        ok, missing = operational_readiness_gate({"rollback": True, "observability": True})
        self.assertFalse(ok)
        self.assertIn("recovery", missing)

    def test_flake_quarantine_separates_nondeterminism_from_repeatable_failure(self) -> None:
        self.assertEqual(flake_classification(failures=2, passes=2, repeated_same_failure=False), "FLAKY_QUARANTINE")
        self.assertEqual(flake_classification(failures=2, passes=0, repeated_same_failure=True), "DETERMINISTIC_FAILURE")

    def test_competitive_profile_activates_only_relevant_w1_controls(self) -> None:
        profile = compile_competitive_profile(mission(), dependency_count=4, uncertainty=0.2)
        self.assertEqual(profile.route_class.value, "PARALLEL")
        self.assertGreater(len(profile.active_gene_ids), 0)
        self.assertNotEqual(len(profile.active_gene_ids), 100)
        self.assertFalse(set(profile.provider_gated_gene_ids) - set(profile.active_gene_ids))
        self.assertIn("source_composition_does_not_prove_provider_runtime", profile.truth_boundary)

    def test_effect_profile_activates_observability_and_platform_delivery(self) -> None:
        item = mission(effect_class="CONSEQUENTIAL_EFFECT", owner_approval_required=True, rollback_required=True, authority_requirements=("explicit-owner-authority",))
        profile = compile_competitive_profile(item, dependency_count=2)
        self.assertIn("OBSERVABILITY", profile.required_control_families)
        self.assertIn("PLATFORM_DELIVERY", profile.required_control_families)
        self.assertEqual(profile.route_class.value, "EFFECT")


if __name__ == "__main__":
    unittest.main()
