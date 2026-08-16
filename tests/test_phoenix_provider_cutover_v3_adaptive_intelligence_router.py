import json
import unittest
from pathlib import Path

from ao_harmonic_v3 import (
    AOHarmonicV3,
    AdaptiveIntelligenceRouter,
    CostClass,
    IntelligenceFeedback,
    IntelligenceSignals,
    IntelligenceTier,
    OpenAI56BindingCatalog,
    ProviderIntelligenceBinding,
    RouterOutcome,
)
from bubbles.forest_background import run_background_event


class AdaptiveIntelligenceRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = AdaptiveIntelligenceRouter()

    def test_routine_low_pressure_stays_cheap(self):
        assessment = self.router.assess(IntelligenceSignals(
            task_id="routine",
            complexity=0.10,
            consequence=0.10,
            uncertainty=0.10,
            dependency_density=0.10,
            adversarial_complexity=0.05,
            evidence_volume=0.05,
            ambiguity=0.10,
            irreversibility=0.05,
            long_horizon=0.10,
            required_accuracy=0.70,
        ))
        self.assertIn(assessment.desired_tier, {IntelligenceTier.INSTANT, IntelligenceTier.MEDIUM})
        self.assertEqual(IntelligenceTier.INSTANT, assessment.minimum_tier)

    def test_high_stakes_legal_has_high_floor(self):
        assessment = self.router.assess(IntelligenceSignals(
            task_id="legal",
            complexity=0.55,
            consequence=0.75,
            uncertainty=0.60,
            dependency_density=0.55,
            adversarial_complexity=0.65,
            high_stakes=True,
            legal_or_regulatory=True,
            required_accuracy=0.96,
        ))
        self.assertGreaterEqual(
            [IntelligenceTier.INSTANT, IntelligenceTier.MEDIUM, IntelligenceTier.HIGH, IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO].index(assessment.desired_tier),
            2,
        )
        self.assertEqual(IntelligenceTier.HIGH, assessment.minimum_tier)

    def test_high_consequence_irreversible_task_has_extra_high_floor(self):
        assessment = self.router.assess(IntelligenceSignals(
            task_id="critical-architecture",
            consequence=0.92,
            uncertainty=0.70,
            irreversibility=0.82,
            adversarial_complexity=0.78,
            required_accuracy=0.98,
        ))
        self.assertGreaterEqual(
            [IntelligenceTier.INSTANT, IntelligenceTier.MEDIUM, IntelligenceTier.HIGH, IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO].index(assessment.minimum_tier),
            3,
        )

    def test_repeated_material_failures_and_contradictions_force_pro(self):
        assessment = self.router.assess(IntelligenceSignals(
            task_id="failure-loop",
            consequence=0.85,
            high_stakes=True,
            repeated_failures=3,
            unresolved_contradictions=3,
        ))
        self.assertEqual(IntelligenceTier.PRO, assessment.minimum_tier)
        self.assertEqual(IntelligenceTier.PRO, assessment.desired_tier)

    def test_feedback_escalates_and_never_crosses_floor_downward(self):
        signals = IntelligenceSignals(
            task_id="legal-feedback",
            high_stakes=True,
            legal_or_regulatory=True,
            consequence=0.70,
            required_accuracy=0.95,
        )
        escalated = self.router.reassess(signals, IntelligenceFeedback(
            quality_score=0.70,
            success=False,
            unresolved_contradictions=1,
        ))
        self.assertIn(escalated.desired_tier, {IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO})
        stable = self.router.reassess(signals, IntelligenceFeedback(
            quality_score=0.99,
            success=True,
            stable_successes=10,
        ))
        self.assertGreaterEqual(
            [IntelligenceTier.INSTANT, IntelligenceTier.MEDIUM, IntelligenceTier.HIGH, IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO].index(stable.desired_tier),
            2,
        )

    def test_stable_low_stakes_success_can_deescalate_one_step(self):
        signals = IntelligenceSignals(
            task_id="routine-success",
            complexity=0.55,
            consequence=0.40,
            uncertainty=0.40,
            dependency_density=0.45,
            required_accuracy=0.85,
        )
        base = self.router.assess(signals)
        stable = self.router.reassess(signals, IntelligenceFeedback(
            quality_score=0.98,
            success=True,
            stable_successes=3,
        ))
        self.assertLessEqual(
            [IntelligenceTier.INSTANT, IntelligenceTier.MEDIUM, IntelligenceTier.HIGH, IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO].index(stable.desired_tier),
            [IntelligenceTier.INSTANT, IntelligenceTier.MEDIUM, IntelligenceTier.HIGH, IntelligenceTier.EXTRA_HIGH, IntelligenceTier.PRO].index(base.desired_tier),
        )

    def test_chatgpt_binding_is_recommendation_not_execution(self):
        signals = IntelligenceSignals(task_id="chatgpt", complexity=0.55, consequence=0.55)
        assessment = self.router.assess(signals)
        bindings = [OpenAI56BindingCatalog.chatgpt(tier) for tier in IntelligenceTier]
        decision = self.router.route(signals, bindings, assessment=assessment)
        self.assertEqual("RECOMMENDATION_READY", decision.state)
        self.assertFalse(decision.execution_allowed)
        self.assertIsNotNone(decision.selected_binding)
        self.assertFalse(decision.selected_binding.programmatic)

    def test_unknown_api_cost_fails_closed_pre_revenue(self):
        signals = IntelligenceSignals(task_id="api", complexity=0.50, consequence=0.50)
        bindings = [OpenAI56BindingCatalog.responses_api(IntelligenceTier.MEDIUM)]
        decision = self.router.route(signals, bindings)
        self.assertFalse(decision.execution_allowed)
        self.assertTrue(decision.owner_approval_required)
        self.assertEqual("HOLD_OWNER_APPROVAL_OR_BINDING_REQUIRED", decision.state)

    def test_cost_or_availability_cannot_drop_below_pro_floor(self):
        signals = IntelligenceSignals(
            task_id="no-silent-downgrade",
            consequence=0.90,
            high_stakes=True,
            repeated_failures=3,
            unresolved_contradictions=3,
        )
        bindings = [
            ProviderIntelligenceBinding(
                binding_id="ONLY_HIGH",
                provider="OPENAI",
                surface="CHATGPT_UI",
                tier=IntelligenceTier.HIGH,
                model="GPT-5.6 Sol",
                programmatic=False,
                cost_class=CostClass.C0_INCLUDED_FREE,
                estimated_monthly_cost=0.0,
                already_paid_or_included=True,
            )
        ]
        decision = self.router.route(signals, bindings)
        self.assertEqual(IntelligenceTier.PRO, decision.assessment.minimum_tier)
        self.assertIsNone(decision.selected_binding)
        self.assertFalse(decision.execution_allowed)

    def test_openai_gpt56_bindings_encode_current_controls(self):
        xhigh = OpenAI56BindingCatalog.responses_api(
            IntelligenceTier.EXTRA_HIGH,
            estimated_monthly_cost=1.0,
        )
        pro = OpenAI56BindingCatalog.responses_api(
            IntelligenceTier.PRO,
            estimated_monthly_cost=1.0,
        )
        self.assertEqual("gpt-5.6", xhigh.model)
        self.assertEqual("xhigh", xhigh.reasoning_effort)
        self.assertIsNone(xhigh.reasoning_mode)
        self.assertEqual("gpt-5.6", pro.model)
        self.assertEqual("pro", pro.reasoning_mode)
        self.assertIsNone(pro.reasoning_effort)

    def test_calibration_never_self_mutates_policy(self):
        outcomes = [
            RouterOutcome(
                selected_tier=IntelligenceTier.HIGH,
                quality_score=0.95,
                required_accuracy=0.90,
                escalation_was_needed=False,
                lower_tier_would_have_sufficed=True,
            )
            for _ in range(10)
        ]
        proposal = self.router.calibration_proposal(outcomes)
        self.assertFalse(proposal["automatic_policy_mutation"])
        self.assertLessEqual(abs(float(proposal["proposed_threshold_shift"])), 0.05)

    def test_runtime_restore_inherits_air(self):
        runtime = AOHarmonicV3()
        acceptance = runtime.restore_acceptance_test()
        self.assertIn("ADAPTIVE_INTELLIGENCE_ROUTER", acceptance["required"])
        self.assertEqual("ADAPTIVE-INTELLIGENCE-ROUTER-V1", acceptance["intelligence_routing"])

    def test_bubbles_low_signal_adds_air_without_provider_execution(self):
        receipt = run_background_event({
            "schema": "BUBBLES-FOREST-BACKGROUND-EVENT-V1",
            "event_id": "evt-air-low",
            "source_class": "FEDERATION_STATE",
            "event_class": "STATE_CHANGE",
            "fingerprint_sha256": "a" * 64,
            "matter_class": "SYSTEM",
            "materiality": 0.20,
            "consequence": 0.25,
            "uncertainty": 0.20,
            "dependency_density": 0.20,
            "adversarial_complexity": 0.10,
            "deadline_risk": False,
            "evidence_risk": False,
            "owner_only": False,
            "provider_readback_missing": False,
            "route_failure": False,
            "objective_exhausted": False,
            "material_strategy_change": False,
            "private_content_included": False,
        })
        self.assertEqual("ADAPTIVE-INTELLIGENCE-ROUTER-V1", receipt["intelligence"]["router_id"])
        self.assertFalse(receipt["intelligence"]["provider_execution_attempted"])
        self.assertFalse(receipt["external_effect"])

    def test_bubbles_legal_deadline_recommends_at_least_extra_high(self):
        receipt = run_background_event({
            "schema": "BUBBLES-FOREST-BACKGROUND-EVENT-V1",
            "event_id": "evt-air-legal",
            "source_class": "GMAIL_METADATA",
            "event_class": "DEADLINE_CHANGE",
            "fingerprint_sha256": "b" * 64,
            "matter_class": "LEGAL",
            "materiality": 0.95,
            "consequence": 0.95,
            "uncertainty": 0.70,
            "dependency_density": 0.60,
            "adversarial_complexity": 0.80,
            "deadline_risk": True,
            "evidence_risk": True,
            "owner_only": False,
            "provider_readback_missing": True,
            "route_failure": False,
            "objective_exhausted": False,
            "material_strategy_change": False,
            "private_content_included": False,
        })
        self.assertIn(receipt["intelligence"]["chatgpt_ui_recommendation"], {"EXTRA_HIGH", "PRO"})
        self.assertIn(receipt["intelligence"]["minimum_quality_floor"], {"EXTRA_HIGH", "PRO"})
        self.assertFalse(receipt["intelligence"]["provider_execution_attempted"])

    def test_governance_and_bootstrap_inherit_air(self):
        policy = json.loads(Path("governance/adaptive_intelligence_router_v1.json").read_text(encoding="utf-8"))
        bootstrap = json.loads(Path("governance/federation_node_bootstrap_v2.json").read_text(encoding="utf-8"))
        self.assertEqual("FEDERATION-ADAPTIVE-INTELLIGENCE-ROUTER-V1", policy["policy_id"])
        self.assertIn("FEDERATION-ADAPTIVE-INTELLIGENCE-ROUTER-V1", bootstrap["inherited_policies"])
        self.assertFalse(policy["learning"]["automatic_policy_mutation"])
        self.assertTrue(bootstrap["cost_governor"]["cannot_silently_degrade_below_air_minimum_quality_floor"])


if __name__ == "__main__":
    unittest.main()
