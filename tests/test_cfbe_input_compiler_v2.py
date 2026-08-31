from __future__ import annotations

import unittest

from federation.cfbe_input_compiler_v2 import (
    InputContext,
    IntentKind,
    compile_owner_input,
)


class CFBEInputCompilerV2Tests(unittest.TestCase):
    def test_n_reuses_verified_active_mission_and_does_not_reask_owner(self):
        context = InputContext(
            active_mission_id="MISSION-42",
            active_objective="Repair Federation coherence",
            available_capabilities=("cfbe-omega", "omega-one"),
        )
        result = compile_owner_input("n", context)
        self.assertIs(result.intent.kind, IntentKind.CONTINUE)
        self.assertEqual(result.mission_ir.mission_id, "MISSION-42")
        self.assertEqual(result.mission_ir.objective, "Repair Federation coherence")
        self.assertFalse(result.intent.owner_clarification_required)
        self.assertIn("choose-highest-value-safe-path", result.workstream_hints)
        self.assertIn("omega-one", result.capability_hints)

    def test_n_without_verified_active_mission_fails_closed_to_clarification_signal(self):
        result = compile_owner_input("n")
        self.assertIs(result.intent.kind, IntentKind.CONTINUE)
        self.assertTrue(result.intent.owner_clarification_required)
        self.assertEqual(result.intent.clarification_reason, "CONTINUATION_HAS_NO_VERIFIED_ACTIVE_MISSION")
        self.assertEqual(result.mission_ir.effect_class, "NO_EFFECT")

    def test_fix_expands_into_root_cause_repair_and_recurrence_work(self):
        result = compile_owner_input("fix the stalled workflow")
        self.assertIs(result.intent.kind, IntentKind.FIX)
        self.assertIn("root cause", result.intent.desired_result.casefold())
        self.assertIn("minimum-safe-repair", result.workstream_hints)
        self.assertIn("prevent-recurrence", result.workstream_hints)
        self.assertIn("recovery", result.capability_hints)

    def test_better_triggers_cfbe_challenger_instead_of_cosmetic_rewrite(self):
        result = compile_owner_input("better")
        self.assertIs(result.intent.kind, IntentKind.IMPROVE)
        self.assertIn("cfbe-omega", result.capability_hints)
        self.assertIn("benchmark-challengers", result.workstream_hints)
        self.assertIn("material improvement", " ".join(result.intent.success_criteria))

    def test_is_this_best_compiles_champion_challenger_mission(self):
        context = InputContext(active_objective="Current orchestration solution")
        result = compile_owner_input("is this the best?", context)
        self.assertIs(result.intent.kind, IntentKind.CHALLENGE)
        self.assertIn("generate-alternatives", result.workstream_hints)
        self.assertIn("cfbe-challenge", result.workstream_hints)
        self.assertEqual(result.mission_ir.effect_class, "NO_EFFECT")

    def test_do_all_means_safe_dependency_ordered_execution_not_unbounded_authority(self):
        context = InputContext(active_objective="Complete the active build")
        result = compile_owner_input("do all", context)
        self.assertIs(result.intent.kind, IntentKind.EXECUTE_ALL)
        self.assertIn("parallelize-independent-lanes", result.workstream_hints)
        self.assertEqual(result.mission_ir.effect_class, "NO_EFFECT")
        self.assertEqual(result.mission_ir.authority_requirements, ())

    def test_build_supplies_expert_engineering_capabilities(self):
        result = compile_owner_input("build an app that tracks evidence")
        self.assertIs(result.intent.kind, IntentKind.BUILD)
        self.assertTrue({"architecture", "software", "testing"}.issubset(set(result.capability_hints)))
        self.assertIn("reuse-before-build", result.workstream_hints)
        self.assertIn("requirements inferred safely", result.intent.success_criteria)

    def test_consequential_send_does_not_inherit_authority(self):
        result = compile_owner_input("send this email to the employer")
        self.assertEqual(result.mission_ir.effect_class, "CONSEQUENTIAL_EFFECT")
        self.assertTrue(result.mission_ir.owner_approval_required)
        self.assertIn("explicit_owner_authority_for_exact_effect", result.mission_ir.authority_requirements)
        self.assertIn("receiver_specific_readback", result.mission_ir.proof_requirements)
        mapping = result.mission_ir.canonical_mapping()
        self.assertFalse(mapping["truth_boundary"]["provider_effect_authorized"])
        self.assertFalse(mapping["truth_boundary"]["publication_authorized"])

    def test_reversible_internal_branch_is_bounded_but_still_requires_route_authority(self):
        result = compile_owner_input("create a branch for the repair")
        self.assertEqual(result.mission_ir.effect_class, "BOUNDED_EFFECT")
        self.assertFalse(result.mission_ir.owner_approval_required)
        self.assertEqual(result.mission_ir.authority_requirements, ("existing_bounded_route_authority",))

    def test_compilation_is_deterministic_for_same_input_and_context(self):
        context = InputContext(active_mission_id="M1", active_objective="Improve evidence quality")
        first = compile_owner_input("n", context)
        second = compile_owner_input("n", context)
        self.assertEqual(first.digest(), second.digest())
        self.assertEqual(first.mission_ir.digest(), second.mission_ir.digest())

    def test_empty_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "CFBE_INPUT_REQUIRED"):
            compile_owner_input("   ")

    def test_truth_boundary_refuses_retraining_and_execution_claims(self):
        result = compile_owner_input("investigate this")
        self.assertIn("compiler_does_not_claim_autonomous_model_retraining", result.truth_boundary)
        self.assertIn("compiler_does_not_execute_or_schedule_work", result.truth_boundary)
        self.assertEqual(result.owner_burden_policy, "NO_AVOIDABLE_OWNER_WORK")


if __name__ == "__main__":
    unittest.main()
