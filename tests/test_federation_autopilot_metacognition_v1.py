import unittest

from benchmarking.cfbe_omega.federation_autopilot_metacognition_v1 import (
    AutonomyLevel,
    ImplementationMode,
    MetaAction,
    MetaCognitiveState,
    autonomy_gate,
    benchmark_summary,
    compile_autopilot_profile,
    compile_implementation_receipt,
    deterministic_receipt_digest,
    load_genome,
    metacognitive_assessment,
    owner_escalation_gate,
    reflection_gate,
    self_modification_gate,
    stagnation_detected,
    terminality_court,
)


class FullAutopilotMetaCognitionV1Tests(unittest.TestCase):
    def _healthy_meta(self) -> MetaCognitiveState:
        return MetaCognitiveState(
            confidence=0.82,
            evidence_coverage=0.90,
            contradiction_pressure=0.10,
            novelty=0.20,
            progress=0.70,
            plan_stability=0.85,
            context_freshness=0.92,
            resource_pressure=0.25,
        )

    def test_exact_100_gene_genome_is_routed_without_authority_inheritance(self):
        genes = load_genome()
        self.assertEqual(100, len(genes))
        self.assertEqual([f"APM-{i:03d}" for i in range(1, 101)], [g.gene_id for g in genes])
        self.assertEqual(10, len({g.control_family for g in genes}))
        receipt = compile_implementation_receipt()
        self.assertEqual(100, receipt.routed_count)
        self.assertEqual(36, receipt.reuse_count)
        self.assertEqual(61, receipt.composed_count)
        self.assertEqual(3, receipt.provider_gated_count)
        self.assertEqual((), receipt.unrouted_gene_ids)
        self.assertFalse(receipt.provider_runtime_proven)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_self_modification_allowed)
        gated = {g.gene_id for g in genes if g.implementation_mode == ImplementationMode.PROVIDER_GATED_CONTRACT}
        self.assertEqual({"APM-005", "APM-033", "APM-058"}, gated)

    def test_metacognition_selects_challenge_evidence_replan_and_rollback_by_state(self):
        challenge = metacognitive_assessment(MetaCognitiveState(0.8, 0.9, 0.8, 0.1, 0.5, 0.8, 0.9, 0.2))
        self.assertEqual(MetaAction.CHALLENGE, challenge.action)
        seek = metacognitive_assessment(MetaCognitiveState(0.8, 0.4, 0.1, 0.1, 0.5, 0.8, 0.9, 0.2))
        self.assertEqual(MetaAction.SEEK_EVIDENCE, seek.action)
        replan = metacognitive_assessment(MetaCognitiveState(0.8, 0.9, 0.1, 0.1, 0.2, 0.3, 0.9, 0.8))
        self.assertEqual(MetaAction.REPLAN, replan.action)
        rollback = metacognitive_assessment(MetaCognitiveState(0.8, 0.9, 0.1, 0.1, 0.5, 0.8, 0.9, 0.2, 3))
        self.assertEqual(MetaAction.ROLLBACK, rollback.action)

    def test_reflection_is_triggered_and_budgeted_not_constant_self_talk(self):
        no_trigger = reflection_gate(trigger_present=False, expected_decision_gain=0.9, estimated_reflection_cost=0.1)
        self.assertFalse(no_trigger.run_reflection)
        useful = reflection_gate(trigger_present=True, expected_decision_gain=0.7, estimated_reflection_cost=0.2)
        self.assertTrue(useful.run_reflection)
        wasteful = reflection_gate(trigger_present=True, expected_decision_gain=0.1, estimated_reflection_cost=0.3)
        self.assertFalse(wasteful.run_reflection)

    def test_autonomy_is_high_for_safe_work_but_external_effects_keep_exact_authority(self):
        safe = autonomy_gate(effect_class="READ_ONLY", reversible=True, exact_authority=False,
                             provider_runtime_available=False, evidence_coverage=0.9)
        self.assertEqual(AutonomyLevel.BOUNDED_AUTOPILOT, safe.level)
        no_authority = autonomy_gate(effect_class="CONSEQUENTIAL", reversible=True, exact_authority=False,
                                     provider_runtime_available=True, evidence_coverage=0.9)
        self.assertEqual(AutonomyLevel.HOLD_OWNER_TRIGGER, no_authority.level)
        no_runtime = autonomy_gate(effect_class="PRIVATE_REVERSIBLE", reversible=True, exact_authority=True,
                                   provider_runtime_available=False, evidence_coverage=0.9)
        self.assertEqual(AutonomyLevel.HOLD_PROVIDER_RUNTIME, no_runtime.level)
        reversible = autonomy_gate(effect_class="PRIVATE_REVERSIBLE", reversible=True, exact_authority=True,
                                   provider_runtime_available=True, evidence_coverage=0.9)
        self.assertEqual(AutonomyLevel.UNATTENDED_REVERSIBLE, reversible.level)
        self.assertTrue(reversible.external_effect_authorized)

    def test_owner_escalation_waits_for_exact_non_delegable_trigger(self):
        continue_work = owner_escalation_gate(safe_routes_remaining=2, exact_owner_decision_required=False,
                                              provider_only_gate=False, safety_or_legal_gate=False)
        self.assertFalse(continue_work.interrupt_owner)
        exact = owner_escalation_gate(safe_routes_remaining=0, exact_owner_decision_required=True,
                                      provider_only_gate=False, safety_or_legal_gate=False)
        self.assertTrue(exact.interrupt_owner)
        self.assertEqual("exact_owner_decision_required", exact.exact_trigger)
        provider_wait = owner_escalation_gate(safe_routes_remaining=0, exact_owner_decision_required=False,
                                              provider_only_gate=True, safety_or_legal_gate=False)
        self.assertFalse(provider_wait.interrupt_owner)
        self.assertTrue(provider_wait.exhausted_safe_routes)

    def test_stagnation_requires_repeated_plan_without_new_evidence(self):
        self.assertTrue(stagnation_detected(["p1", "p1", "p1"], ["e1", "e1", "e1"]))
        self.assertFalse(stagnation_detected(["p1", "p1", "p2"], ["e1", "e1", "e1"]))
        self.assertFalse(stagnation_detected(["p1", "p1", "p1"], ["e1", "e2", "e3"]))

    def test_terminality_requires_semantic_fruit_proof_and_no_critical_conflict(self):
        done = terminality_court(objective_satisfied=True, semantic_readback=True, proof_complete=True,
                                 unresolved_critical_contradictions=0, external_effect_pending=False)
        self.assertTrue(done.terminal)
        self.assertEqual("VERIFIED_COMPLETE", done.state)
        held = terminality_court(objective_satisfied=True, semantic_readback=False, proof_complete=True,
                                 unresolved_critical_contradictions=1, external_effect_pending=False)
        self.assertFalse(held.terminal)
        self.assertEqual(("semantic_readback", "critical_contradictions"), held.missing)

    def test_self_modification_can_reach_review_but_never_self_promotes_stable_state(self):
        decision = self_modification_gate(baseline_score=0.70, candidate_score=0.84, paired_cases=30,
                                          hard_regressions=0, rollback_available=True,
                                          independent_verifier_pass=True, observed_value_positive=True)
        self.assertEqual("CANDIDATE_STABLE_REVIEW", decision.state)
        self.assertFalse(decision.stable_promotion_allowed)
        regression = self_modification_gate(baseline_score=0.70, candidate_score=0.90, paired_cases=30,
                                            hard_regressions=1, rollback_available=True,
                                            independent_verifier_pass=True, observed_value_positive=True)
        self.assertEqual("REJECT_REGRESSION", regression.state)
        self.assertTrue(regression.rollback_required)

    def test_profile_compiles_autopilot_metacognition_and_evolution_without_provider_claim(self):
        state = MetaCognitiveState(0.75, 0.9, 0.75, 0.1, 0.6, 0.8, 0.9, 0.2)
        profile = compile_autopilot_profile(
            mission_id="mission-auto-1",
            effect_class="READ_ONLY",
            reversible=True,
            exact_authority=False,
            provider_runtime_available=False,
            evidence_coverage=0.9,
            meta_state=state,
        )
        self.assertEqual(AutonomyLevel.BOUNDED_AUTOPILOT, profile.autonomy.level)
        self.assertEqual(MetaAction.CHALLENGE, profile.metacognition.action)
        self.assertIn("APM-091", profile.active_gene_ids)
        self.assertIn("APM-005", profile.provider_gated_gene_ids)
        self.assertTrue(any("does_not_grant_external_effect_authority" in item for item in profile.truth_boundary))

    def test_benchmark_is_strict_and_exposes_runtime_and_calibration_gaps(self):
        summary = benchmark_summary()
        self.assertEqual(15, summary["dimension_count"])
        self.assertEqual(84.87, summary["architecture_average"])
        self.assertEqual(65.6, summary["proof_adjusted_average"])
        self.assertIn("Durable unattended execution", summary["lowest_proof_dimensions"])
        self.assertIn("Self-capability & authority awareness", summary["highest_proof_dimensions"])
        self.assertFalse(summary["vendor_certified"])
        self.assertFalse(summary["full_autopilot_runtime_proven"])
        self.assertFalse(summary["private_chain_of_thought_required"])

    def test_receipt_digest_is_deterministic(self):
        mapping = compile_implementation_receipt().canonical_mapping()
        self.assertEqual(deterministic_receipt_digest(mapping), deterministic_receipt_digest(mapping))
        altered = dict(mapping)
        altered["routed_count"] = 99
        self.assertNotEqual(deterministic_receipt_digest(mapping), deterministic_receipt_digest(altered))


if __name__ == "__main__":
    unittest.main()
