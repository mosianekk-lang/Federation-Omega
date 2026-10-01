from __future__ import annotations

import unittest

from sol_61_runtime.sol_62_intelligence_amplifier import (
    CognitionProfile,
    ReasoningMode,
    compile_intelligence_plan,
    module_summary,
)


class Sol62IntelligenceAmplifierTests(unittest.TestCase):
    def test_low_complexity_uses_small_direct_budget(self):
        plan = compile_intelligence_plan(CognitionProfile(
            complexity=0.1, stakes=0.1, uncertainty=0.1,
            novelty=0.1, evidence_gap=0.1, reversibility=1.0,
        ))
        self.assertEqual(plan.mode, ReasoningMode.DIRECT)
        self.assertLessEqual(plan.reasoning_budget, 3)
        self.assertEqual(plan.max_parallel_strategies, 1)

    def test_high_stakes_irreversible_work_forces_adversarial_proof(self):
        plan = compile_intelligence_plan(CognitionProfile(
            complexity=0.8, stakes=0.95, uncertainty=0.8,
            novelty=0.7, evidence_gap=0.8, reversibility=0.1,
            multi_domain=True,
        ))
        self.assertEqual(plan.mode, ReasoningMode.ADVERSARIAL)
        self.assertGreaterEqual(plan.reasoning_budget, 6)
        self.assertTrue(plan.independent_verifier_required)
        self.assertIn("ADVERSARIAL_PROOF", {x.strategy_id for x in plan.selected_strategies})
        self.assertIn("FAIL_CLOSED_ON_AMBIGUITY", plan.required_checks)

    def test_scientific_mode_for_high_uncertainty_and_evidence_gap(self):
        plan = compile_intelligence_plan(CognitionProfile(
            complexity=0.55, stakes=0.45, uncertainty=0.9,
            novelty=0.65, evidence_gap=0.9, reversibility=0.8,
        ))
        self.assertEqual(plan.mode, ReasoningMode.SCIENTIFIC)
        self.assertIn("UNCERTAINTY_CALIBRATION", plan.required_checks)
        self.assertIn("COUNTERFACTUAL_OR_FALSIFIER", plan.required_checks)

    def test_strategy_families_are_diverse(self):
        plan = compile_intelligence_plan(CognitionProfile(
            complexity=0.9, stakes=0.7, uncertainty=0.8,
            novelty=0.9, evidence_gap=0.8, reversibility=0.5,
            multi_domain=True,
        ), max_parallel=3)
        families = [x.family for x in plan.selected_strategies]
        self.assertEqual(len(families), len(set(families)))
        self.assertEqual(len(families), 3)

    def test_time_pressure_cannot_erase_high_assurance_floor(self):
        plan = compile_intelligence_plan(CognitionProfile(
            complexity=0.8, stakes=0.95, uncertainty=0.7,
            novelty=0.7, evidence_gap=0.7, time_pressure=1.0,
            reversibility=0.1,
        ))
        self.assertGreaterEqual(plan.reasoning_budget, 6)
        self.assertTrue(plan.independent_verifier_required)

    def test_deterministic_plan_identity(self):
        p = CognitionProfile(
            complexity=0.62, stakes=0.61, uncertainty=0.57,
            novelty=0.42, evidence_gap=0.51,
        )
        self.assertEqual(
            compile_intelligence_plan(p).plan_id,
            compile_intelligence_plan(p).plan_id,
        )

    def test_no_authority_or_truth_root_expansion(self):
        plan = compile_intelligence_plan(CognitionProfile())
        self.assertFalse(plan.authority_expansion)
        self.assertFalse(plan.provider_effect_authorized)
        self.assertFalse(plan.goal_mutation_allowed)
        self.assertFalse(plan.truth_root_replacement_allowed)
        self.assertFalse(plan.chain_of_thought_exposure_allowed)

        summary = module_summary()
        self.assertEqual(summary["external_algorithm_cohort"], "HG-EXTALG-001..100")
        self.assertFalse(summary["authority_expansion"])
        self.assertFalse(summary["truth_root_replacement_allowed"])


if __name__ == "__main__":
    unittest.main()
