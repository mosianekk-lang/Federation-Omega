from __future__ import annotations

import unittest

from sol_61_runtime.sol_62_intelligence_amplifier import (
    AttemptTrace,
    DecisionOption,
    EvidenceSignal,
    Hypothesis,
    InvestigationAction,
    CognitionProfile,
    assess_hypotheses,
    calibrated_confidence,
    choose_next_investigation,
    compile_intelligence_plan,
    detect_stagnation,
    robust_choice,
)


class Sol62IntelligenceAmplifierV2Tests(unittest.TestCase):
    def test_hypothesis_tournament_penalizes_contradiction_and_correlation(self):
        hypotheses = (Hypothesis("A", 0.5), Hypothesis("B", 0.5))
        evidence = (
            EvidenceSignal("a1", "A", "SUPPORT", "provider", 0.95, 0.95, 1.0),
            EvidenceSignal("a2", "A", "SUPPORT", "runtime", 0.90, 0.90, 1.0),
            EvidenceSignal("b1", "B", "SUPPORT", "provider", 0.95, 0.35, 1.0),
            EvidenceSignal("b2", "B", "CONTRADICT", "runtime", 0.90, 0.90, 1.0),
        )
        ranked = assess_hypotheses(hypotheses, evidence)
        self.assertEqual(ranked[0].hypothesis_id, "A")
        b = next(x for x in ranked if x.hypothesis_id == "B")
        self.assertTrue(b.unresolved_contradiction)
        self.assertLess(b.confidence_cap, 0.9)

    def test_value_of_information_prefers_discriminating_low_cost_action(self):
        decision = choose_next_investigation((
            InvestigationAction("cheap", 0.8, 0.9, 1.0, 0.2, 0.2, 0.1),
            InvestigationAction("broad", 0.7, 0.4, 0.5, 0.9, 0.9, 0.4),
        ))
        self.assertTrue(decision.continue_investigation)
        self.assertEqual(decision.action_id, "cheap")

    def test_low_information_gain_stops_search(self):
        decision = choose_next_investigation((
            InvestigationAction("noise", 0.02, 0.2, 1.0, 0.1, 0.1, 0.1),
        ), minimum_information_gain=0.08)
        self.assertFalse(decision.continue_investigation)
        self.assertEqual(decision.reason, "MARGINAL_INFORMATION_GAIN_BELOW_THRESHOLD")

    def test_fragile_winner_is_held(self):
        decision = robust_choice((
            DecisionOption("A", 0.80, 0.40, 0.20, 0.7),
            DecisionOption("B", 0.78, 0.38, 0.19, 0.7),
        ), minimum_margin=0.08)
        self.assertFalse(decision.stable)
        self.assertIsNone(decision.selected_option_id)
        self.assertEqual(decision.reason, "FRAGILE_WINNER_HOLD")

    def test_clear_robust_winner_can_pass(self):
        decision = robust_choice((
            DecisionOption("A", 0.92, 0.10, 0.05, 0.9),
            DecisionOption("B", 0.65, 0.35, 0.30, 0.4),
        ))
        self.assertTrue(decision.stable)
        self.assertEqual(decision.selected_option_id, "A")

    def test_repeated_low_gain_same_mechanism_forces_mutation(self):
        decision = detect_stagnation((
            AttemptTrace("SEARCH", "same", 0.01),
            AttemptTrace("SEARCH", "same", 0.02),
            AttemptTrace("SEARCH", "same", 0.01),
        ))
        self.assertTrue(decision.stagnating)
        self.assertTrue(decision.change_strategy_required)
        self.assertEqual(decision.reason, "CHANGED_MECHANISM_REQUIRED")

    def test_material_change_clears_stagnation(self):
        decision = detect_stagnation((
            AttemptTrace("SEARCH", "same", 0.01),
            AttemptTrace("SEARCH", "same", 0.02, materially_changed=True),
            AttemptTrace("SEARCH", "same", 0.01),
        ))
        self.assertFalse(decision.stagnating)

    def test_confidence_is_capped_by_weak_calibration_and_contradiction(self):
        confidence = calibrated_confidence(
            0.97,
            independent_domains=1,
            contradiction_mass=0.8,
            historical_brier=0.35,
            calibration_samples=10,
        )
        self.assertLess(confidence, 0.8)

    def test_complex_uncertain_plan_requires_v2_meta_checks(self):
        plan = compile_intelligence_plan(CognitionProfile(
            complexity=0.9, stakes=0.7, uncertainty=0.8,
            novelty=0.7, evidence_gap=0.8, reversibility=0.5,
        ))
        self.assertIn("VALUE_OF_INFORMATION_NEXT_ACTION", plan.required_checks)
        self.assertIn("EVIDENCE_DIVERSITY_CONFIDENCE_CAP", plan.required_checks)
        self.assertIn("ROBUSTNESS_SENSITIVITY_GATE", plan.required_checks)
        self.assertIn("STAGNATION_MUTATION_GUARD", plan.required_checks)


if __name__ == "__main__":
    unittest.main()
