from __future__ import annotations

import unittest

from federation.idea_to_system_compiler import (
    CapabilityRecord,
    capability_gap_plan,
    compile_idea_to_system,
    infer_intent,
)


class IdeaToSystemCompilerTests(unittest.TestCase):
    def test_blank_idea_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "IDEA_REQUIRED"):
            infer_intent("   ")

    def test_software_automation_data_intent_is_compiled(self) -> None:
        intent = infer_intent(
            "Build an automated invoice reconciliation app that compares spreadsheet data and produces exceptions."
        )
        self.assertIn("SOFTWARE_BUILD", intent.intent_classes)
        self.assertIn("AUTOMATION", intent.intent_classes)
        self.assertIn("DATA", intent.intent_classes)
        self.assertIn("CODE_SANDBOX", intent.required_capabilities)
        self.assertIn("WORKFLOW_ORCHESTRATION", intent.required_capabilities)
        self.assertIn("DATA_INTEGRATION", intent.required_capabilities)
        self.assertIn("TARGET_RUNTIME", intent.unknowns)

    def test_gap_planner_prefers_reuse_then_extend_then_smallest_build(self) -> None:
        records = (
            CapabilityRecord(
                "CAP-INTENT",
                "Intent compiler",
                ("INTENT_COMPILATION",),
                evidence_state="CURRENT_STABLE",
            ),
            CapabilityRecord(
                "CAP-SANDBOX",
                "Code sandbox candidate",
                ("CODE_SANDBOX",),
                evidence_state="CANDIDATE",
            ),
        )
        decisions = {
            item.requirement: item
            for item in capability_gap_plan(
                ("INTENT_COMPILATION", "CODE_SANDBOX", "DATA_INTEGRATION"),
                records,
            )
        }
        self.assertEqual(decisions["INTENT_COMPILATION"].strategy, "REUSE")
        self.assertEqual(decisions["CODE_SANDBOX"].strategy, "EXTEND")
        self.assertEqual(decisions["DATA_INTEGRATION"].strategy, "DISCOVER_THEN_BUILD_SMALLEST")

    def test_compile_is_deterministic_and_does_not_grant_authority(self) -> None:
        records = (
            CapabilityRecord("CAP-A", "Intent", ("INTENT_COMPILATION",), "VERIFIED"),
            CapabilityRecord("CAP-B", "Sandbox", ("CODE_SANDBOX",), "CANDIDATE"),
        )
        idea = "Build and automate a small API for reconciling invoice data."
        left = compile_idea_to_system(idea, records, source_frontier="main@test")
        right = compile_idea_to_system(idea, tuple(reversed(records)), source_frontier="main@test")
        self.assertEqual(left.digest(), right.digest())
        truth = left.mission_ir.canonical_mapping()["truth_boundary"]
        self.assertFalse(truth["authority_inherited"])
        self.assertFalse(truth["provider_effect_authorized"])
        self.assertFalse(truth["publication_authorized"])

    def test_consequential_effect_requires_owner_gate(self) -> None:
        plan = compile_idea_to_system(
            "Build the release and deploy to production, then publish it.",
            source_frontier="main@test",
        )
        self.assertEqual(plan.mission_ir.effect_class, "CONSEQUENTIAL_EFFECT")
        self.assertTrue(plan.mission_ir.owner_approval_required)
        self.assertIn("TARGET_EFFECT_AUTHORITY", plan.mission_ir.authority_requirements)
        self.assertIn("ROLLBACK_RECEIPT", plan.mission_ir.proof_requirements)
        self.assertTrue(plan.owner_questions)

    def test_read_only_research_does_not_invent_effect_authority(self) -> None:
        plan = compile_idea_to_system(
            "Research and compare current agent orchestration patterns.",
            source_frontier="main@test",
        )
        self.assertEqual(plan.mission_ir.effect_class, "READ_ONLY")
        self.assertFalse(plan.mission_ir.owner_approval_required)
        self.assertEqual(plan.mission_ir.authority_requirements, ())
        self.assertFalse(plan.mission_ir.rollback_required)

    def test_plan_preserves_minimum_build_policy(self) -> None:
        plan = compile_idea_to_system(
            "Create a document workflow that researches sources and generates a reviewable report.",
            source_frontier="main@test",
        )
        strategies = {decision.strategy for decision in plan.capability_decisions}
        self.assertIn("DISCOVER_THEN_BUILD_SMALLEST", strategies)
        self.assertIn("DISCOVER_CURRENT_RESOURCES_FOR_UNSATISFIED_GAPS", plan.autonomous_steps)
        self.assertIn("BUILD_ONLY_SMALLEST_REMAINING_GAPS", plan.autonomous_steps)


if __name__ == "__main__":
    unittest.main()
