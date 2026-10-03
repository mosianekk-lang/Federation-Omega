import unittest

from sovara.creative import (
    ConstraintDisposition,
    ConstraintKind,
    CreativeIntentContract,
    PlatformConstraint,
    StudioRequest,
    ContentClass,
    PrivacyClass,
    compile_creative_freedom_plan,
    compile_studio_plan,
)


class CreativeFreedomRoutingTests(unittest.TestCase):
    def test_tool_limit_routes_around_without_rewriting_objective(self):
        intent = CreativeIntentContract(
            request_id="CF-001",
            objective="Create the exact cinematic garment campaign specified by the creator",
            required_modalities=("image", "video", "layout"),
        )
        plan = compile_creative_freedom_plan(
            intent,
            (
                PlatformConstraint(
                    source="provider-a",
                    kind=ConstraintKind.TOOL_FEATURE,
                    description="native editor lacks the requested compositing feature",
                ),
            ),
        )
        self.assertEqual(plan.canonical_objective, intent.objective)
        self.assertTrue(plan.objective_preserved)
        self.assertFalse(plan.platform_constraints_may_rewrite_goal)
        self.assertFalse(plan.provider_lock_in_allowed)
        self.assertEqual(
            plan.route_actions[0].disposition,
            ConstraintDisposition.ROUTE_AROUND,
        )

    def test_format_limit_is_transcoded_not_treated_as_design_limit(self):
        plan = compile_creative_freedom_plan(
            CreativeIntentContract(request_id="CF-002", objective="Preserve the full editable master"),
            (
                PlatformConstraint(
                    source="tool-b",
                    kind=ConstraintKind.PLATFORM_FORMAT,
                    description="tool exports a narrower interchange format",
                ),
            ),
        )
        self.assertEqual(plan.route_actions[0].disposition, ConstraintDisposition.TRANSCODE)
        self.assertFalse(plan.execution_held)

    def test_hard_boundary_holds_execution_but_preserves_design_intent(self):
        objective = "Produce the creator-defined final composition"
        plan = compile_creative_freedom_plan(
            CreativeIntentContract(request_id="CF-003", objective=objective),
            (
                PlatformConstraint(
                    source="provider-policy",
                    kind=ConstraintKind.POLICY,
                    description="current route is not authorized for this operation",
                    hard_boundary=True,
                ),
            ),
        )
        self.assertTrue(plan.execution_held)
        self.assertEqual(plan.canonical_objective, objective)
        self.assertEqual(
            plan.route_actions[0].disposition,
            ConstraintDisposition.HOLD_EXECUTION,
        )

    def test_studio_plan_is_platform_independent_by_default(self):
        plan = compile_studio_plan(
            StudioRequest(
                request_id="CF-004",
                objective="Create a platform-independent visual identity system",
                content_class=ContentClass.IMAGE,
                privacy_class=PrivacyClass.INTERNAL,
            )
        )
        self.assertTrue(plan.creative_intent_preserved)
        self.assertFalse(plan.provider_lock_in_allowed)
        self.assertEqual(plan.platform_constraint_treatment, "ROUTE_AROUND_NOT_GOAL_REWRITE")
        self.assertEqual(plan.canonical_intermediate_representation, "FUSE_CREATIVE_IR_V1")


if __name__ == "__main__":
    unittest.main()
