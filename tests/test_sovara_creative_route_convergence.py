from __future__ import annotations

import unittest

from sovara.creative.policy import ContentClass, PrivacyClass, RoutePolicy, RouteType
from sovara.creative.router import RouteDecision, select_route
from sovara.creative.sovereign_studio import ExecutionPlane, StudioRequest, compile_studio_plan


class SovaraCreativeRouteConvergenceTests(unittest.TestCase):
    def request(self, *, privacy=PrivacyClass.INTERNAL) -> StudioRequest:
        return StudioRequest(
            request_id="SC-ROUTE-CONVERGENCE-001",
            objective="Build a bounded creative package",
            content_class=ContentClass.IMAGE,
            privacy_class=privacy,
        )

    def test_studio_consumes_canonical_router_decision_without_inventing_fallback(self) -> None:
        candidates = (
            RoutePolicy(
                route_id="sovereign",
                route_type=RouteType.SELF_HOSTED_GCP,
                privacy_ceiling=PrivacyClass.PRIVATE_ASSET,
                policy_verified=True,
            ),
            RoutePolicy(
                route_id="openrouter",
                route_type=RouteType.OPENROUTER_FCX,
                privacy_ceiling=PrivacyClass.INTERNAL,
                policy_verified=True,
            ),
        )
        decision = select_route(
            content_class=ContentClass.IMAGE,
            privacy_class=PrivacyClass.INTERNAL,
            candidates=candidates,
        )
        plan = compile_studio_plan(self.request(), route_decision=decision)
        self.assertTrue(plan.route_decision_bound)
        self.assertEqual("sovereign", plan.selected_route_id)
        self.assertEqual(RouteType.SELF_HOSTED_GCP.value, plan.selected_route_type)
        self.assertEqual(ExecutionPlane.PRIVATE_MODEL_CELL, plan.primary_plane)
        self.assertEqual((), plan.fallback_planes)

    def test_openrouter_decision_maps_to_mainstream_frontier_only_for_eligible_privacy(self) -> None:
        decision = RouteDecision(
            selected_route_id="openrouter",
            selected_route_type=RouteType.OPENROUTER_FCX.value,
            eligibility="ELIGIBLE",
            evaluated=(("openrouter", "ELIGIBLE"),),
            no_paper_continuity_preserved=True,
            reason="eligible_route_selected",
        )
        plan = compile_studio_plan(self.request(), route_decision=decision)
        self.assertEqual(ExecutionPlane.MAINSTREAM_FRONTIER, plan.primary_plane)
        with self.assertRaisesRegex(ValueError, "private studio privacy ceiling"):
            compile_studio_plan(self.request(privacy=PrivacyClass.PRIVATE_ASSET), route_decision=decision)

    def test_secret_request_rejects_external_canonical_route(self) -> None:
        decision = RouteDecision(
            selected_route_id="tool",
            selected_route_type=RouteType.CREATIVE_TOOL_ADAPTER.value,
            eligibility="ELIGIBLE",
            evaluated=(("tool", "ELIGIBLE"),),
            no_paper_continuity_preserved=True,
            reason="eligible_route_selected",
        )
        with self.assertRaisesRegex(ValueError, "SECRET studio privacy ceiling"):
            compile_studio_plan(self.request(privacy=PrivacyClass.SECRET), route_decision=decision)

    def test_empty_route_decision_fails_closed(self) -> None:
        decision = RouteDecision(
            selected_route_id=None,
            selected_route_type=None,
            eligibility="INELIGIBLE",
            evaluated=(),
            no_paper_continuity_preserved=True,
            reason="no_currently_eligible_route",
        )
        with self.assertRaisesRegex(ValueError, "selected eligible route"):
            compile_studio_plan(self.request(), route_decision=decision)

    def test_legacy_source_only_plan_is_explicitly_unbound(self) -> None:
        plan = compile_studio_plan(self.request())
        self.assertFalse(plan.route_decision_bound)
        self.assertIsNone(plan.selected_route_id)
        self.assertIsNone(plan.selected_route_type)


if __name__ == "__main__":
    unittest.main()
