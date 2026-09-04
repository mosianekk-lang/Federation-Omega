import unittest

from ao_harmonic_v3 import (
    HUMAN_FIRST_OMEGA_ID,
    HumanFirstAOHarmonicV3,
    ForestOmegaContext,
    bootstrap_human_first,
)
from federation_consolidation.human_first_omega import ActionProposal, HumanMissionContract


class HumanFirstAOBindingTests(unittest.TestCase):
    def context(self, **overrides):
        data = dict(
            matter_id="HFO-AO-TEST",
            objective="Protect the human mission while doing the necessary strategic work",
            desired_outcome="Verified objective progress with minimal avoidable owner burden",
            high_stakes=False,
            consequential_action_planned=False,
            route_alternatives=(),
        )
        data.update(overrides)
        return ForestOmegaContext(**data)

    def test_runtime_exposes_human_first_above_existing_forest(self):
        runtime = HumanFirstAOHarmonicV3()
        self.assertEqual(runtime.human_first.ENGINE_ID, HUMAN_FIRST_OMEGA_ID)
        self.assertEqual(runtime.human_first.forest, runtime.forest)
        self.assertEqual(runtime.forest.ENGINE_ID, "FOREST-FIRST-OMEGA-V1")

    def test_safe_internal_reasoning_continues_without_owner_interrupt(self):
        runtime = HumanFirstAOHarmonicV3()
        result = runtime.run_human_first_forest(self.context())
        self.assertFalse(result.user_interrupt_required)
        self.assertTrue(result.gate["allow"])
        self.assertFalse(result.gate["human_required"])
        self.assertEqual(result.forest.engine_id, "FOREST-FIRST-OMEGA-V1")
        self.assertFalse(result.external_effect)

    def test_unnecessary_requested_interrupt_is_suppressed(self):
        runtime = HumanFirstAOHarmonicV3()
        action = ActionProposal(
            action_id="SAFE-INTERRUPT",
            description="Safe internal work that unnecessarily requested the owner",
            requested_owner_interrupt=True,
        )
        result = runtime.run_human_first_forest(self.context(), action=action)
        self.assertFalse(result.user_interrupt_required)
        self.assertTrue(result.gate["allow"])
        self.assertTrue(result.gate["suppress_interrupt"])
        self.assertEqual(result.gate["mode"], "AUTO_CONTINUE_SILENT")

    def test_consequential_forest_continuation_requires_human_judgment(self):
        runtime = HumanFirstAOHarmonicV3()
        result = runtime.run_human_first_forest(
            self.context(consequential_action_planned=True)
        )
        self.assertTrue(result.user_interrupt_required)
        self.assertFalse(result.gate["allow"])
        self.assertTrue(result.gate["human_required"])
        self.assertIn("AUTHORITY_CEILING_EXCEEDED", result.gate["reasons"])
        self.assertIn("CONSEQUENTIAL_ACTION", result.gate["reasons"])

    def test_high_stakes_missing_teachback_requires_human(self):
        runtime = HumanFirstAOHarmonicV3()
        result = runtime.run_human_first_forest(
            self.context(high_stakes=True, teach_back_complete=False)
        )
        self.assertTrue(result.user_interrupt_required)
        self.assertIn("TEACH_BACK_REQUIRED", result.gate["reasons"])

    def test_explicit_external_effect_is_held_and_missing_readback_is_visible(self):
        runtime = HumanFirstAOHarmonicV3()
        contract = HumanMissionContract(
            mission_id="EXTERNAL-TEST",
            owner="Kim Kagiso Mosiane",
            intent="Preserve human control over an external effect",
            success_conditions=("Effect occurs only after human judgment and readback",),
            authority_ceiling="A1_INTERNAL",
        )
        action = ActionProposal(
            action_id="EXTERNAL-ACTION",
            description="Proposed external provider effect",
            authority_required="A2_EXTERNAL_REVERSIBLE",
            external_effect=True,
            readback_plan_present=False,
        )
        result = runtime.run_human_first_forest(
            self.context(), contract=contract, action=action
        )
        self.assertTrue(result.user_interrupt_required)
        self.assertIn("EXTERNAL_EFFECT", result.gate["reasons"])
        self.assertIn("READBACK_PLAN_REQUIRED", result.gate["reasons"])

    def test_restore_acceptance_declares_human_first_without_runtime_overclaim(self):
        acceptance = HumanFirstAOHarmonicV3().restore_acceptance_test()
        self.assertEqual(acceptance["human_control_plane"], HUMAN_FIRST_OMEGA_ID)
        self.assertIn("HUMAN_FIRST_OMEGA", acceptance["required"])
        self.assertIn("HUMAN_MISSION_CONTRACT", acceptance["required"])
        self.assertTrue(acceptance["human_first_source_bound"])
        self.assertFalse(acceptance["human_first_provider_runtime_bound"])
        self.assertFalse(acceptance["human_value_improvement_measured"])

    def test_bootstrap_preserves_exact_truth_boundary(self):
        payload = bootstrap_human_first()
        self.assertEqual(payload["human_control_plane"], HUMAN_FIRST_OMEGA_ID)
        self.assertTrue(payload["truth_boundary"]["human_first_source_bound"])
        self.assertFalse(payload["truth_boundary"]["human_first_provider_runtime_bound"])
        self.assertFalse(payload["truth_boundary"]["cross_surface_enforcement_proved"])
        self.assertFalse(payload["truth_boundary"]["external_effect_authority_expanded"])


if __name__ == "__main__":
    unittest.main()
