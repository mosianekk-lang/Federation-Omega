from __future__ import annotations

import unittest

from evidenceops.caseforge.capability_decision import (
    BlockerKind,
    CapabilityDecisionRequest,
    CapabilityResolutionGate,
    CapabilityScope,
    CapabilityState,
    GateDecision,
    RouteAttempt,
    TerminalClaim,
)


class CapabilityResolutionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = CapabilityResolutionGate()

    def test_invalid_argument_cannot_be_promoted_to_objective_incapability(self) -> None:
        decision = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="read a control row",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.LOCAL_TOOL_CALL,
                state=CapabilityState.ROUTE_CALLABLE,
                blocker=BlockerKind.INVALID_ARGUMENT_OR_SCHEMA,
                route_attempts=(
                    RouteAttempt(
                        route_id="sheets:wrong-tab",
                        blocker=BlockerKind.INVALID_ARGUMENT_OR_SCHEMA,
                        evidence_ref="ERR-400",
                    ),
                ),
            )
        )
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, decision.decision)
        self.assertIn("invalid", decision.allowed_language.lower())
        self.assertFalse(decision.manual_user_action_allowed)

    def test_approval_required_is_not_incapability(self) -> None:
        decision = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="send an external email",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.CONNECTED_PROVIDER,
                state=CapabilityState.ROUTE_CALLABLE,
                blocker=BlockerKind.APPROVAL_OR_PERMISSION_REQUIRED,
            )
        )
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, decision.decision)
        self.assertIn("approval", decision.allowed_language.lower())

    def test_can_requires_readback_not_architecture_or_connection_only(self) -> None:
        denied = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="write to a provider surface",
                claim=TerminalClaim.CAN,
                scope=CapabilityScope.CONNECTED_PROVIDER,
                state=CapabilityState.CONNECTOR_DISCOVERED,
                current_discovery_ref="CONNECTOR-1",
            )
        )
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, denied.decision)

        allowed = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="write to a provider surface",
                claim=TerminalClaim.CAN,
                scope=CapabilityScope.CONNECTED_PROVIDER,
                state=CapabilityState.READBACK_VERIFIED,
                provider_readback_ref="RCP-WRITE-1",
                route_attempts=(
                    RouteAttempt(
                        route_id="provider-write",
                        succeeded=True,
                        readback_verified=True,
                        evidence_ref="RCP-WRITE-1",
                    ),
                ),
            )
        )
        self.assertEqual(GateDecision.ALLOW_BOUNDED, allowed.decision)

    def test_done_requires_objective_complete_zero_internal_dependencies_and_readback(self) -> None:
        denied = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="complete a mission",
                claim=TerminalClaim.DONE,
                scope=CapabilityScope.USER_CANONICAL_SYSTEM,
                state=CapabilityState.READBACK_VERIFIED,
                provider_readback_ref="RCP-CHILD",
                internal_executable_dependencies=1,
            )
        )
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, denied.decision)
        self.assertIn("DONE_REQUIRES_OBJECTIVE_COMPLETE_STATE", denied.reason_codes)
        self.assertIn("DONE_REQUIRES_ZERO_EXECUTABLE_INTERNAL_DEPENDENCIES", denied.reason_codes)

        allowed = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="complete a mission",
                claim=TerminalClaim.DONE,
                scope=CapabilityScope.USER_CANONICAL_SYSTEM,
                state=CapabilityState.OBJECTIVE_COMPLETE,
                provider_readback_ref="RCP-MISSION-CLOSE",
                internal_executable_dependencies=0,
            )
        )
        self.assertEqual(GateDecision.ALLOW_BOUNDED, allowed.decision)

    def test_platform_hard_limit_must_be_exact_scope_and_equivalent_routes_checked(self) -> None:
        denied = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="rewrite global platform policy",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.PLATFORM_GLOBAL,
                state=CapabilityState.UNKNOWN,
                blocker=BlockerKind.PLATFORM_HARD_LIMIT,
                current_discovery_ref="PRODUCT-BOUNDARY",
                exact_platform_scope=True,
                equivalent_routes_checked=False,
            )
        )
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, denied.decision)
        self.assertIn("PLATFORM_LIMIT_REQUIRES_EQUIVALENT_ROUTE_CHECK", denied.reason_codes)

        allowed = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="rewrite global platform policy",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.PLATFORM_GLOBAL,
                state=CapabilityState.UNKNOWN,
                blocker=BlockerKind.PLATFORM_HARD_LIMIT,
                current_discovery_ref="PRODUCT-BOUNDARY",
                exact_platform_scope=True,
                equivalent_routes_checked=True,
            )
        )
        self.assertEqual(GateDecision.ALLOW_BOUNDED, allowed.decision)
        self.assertIn("exact platform-level action", allowed.allowed_language.lower())

    def test_route_space_exhaustion_requires_current_discovery_and_attempt_ledger(self) -> None:
        denied = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="retrieve an unavailable provider object",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.CONNECTED_PROVIDER,
                state=CapabilityState.UNKNOWN,
                blocker=BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED,
                equivalent_routes_checked=True,
            )
        )
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, denied.decision)

        allowed = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="retrieve an unavailable provider object",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.CONNECTED_PROVIDER,
                state=CapabilityState.UNKNOWN,
                blocker=BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED,
                current_discovery_ref="DISCOVERY-RCP-1",
                equivalent_routes_checked=True,
                manual_user_action_proposed=True,
                route_attempts=(
                    RouteAttempt(
                        route_id="connector-direct",
                        blocker=BlockerKind.AUTHENTICATION_OR_CONNECTION_REQUIRED,
                        evidence_ref="ERR-AUTH",
                    ),
                    RouteAttempt(
                        route_id="canonical-bridge",
                        blocker=BlockerKind.EXTERNAL_DEPENDENCY,
                        evidence_ref="ERR-NOT-PRESENT",
                    ),
                ),
            )
        )
        self.assertEqual(GateDecision.ALLOW_BOUNDED, allowed.decision)
        self.assertTrue(allowed.manual_user_action_allowed)
        self.assertIn("2_DISTINCT_ROUTES", "|".join(allowed.reason_codes))

    def test_verified_success_contradicts_route_exhaustion(self) -> None:
        decision = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="retrieve control state",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.CURRENT_CHAT,
                state=CapabilityState.READBACK_VERIFIED,
                blocker=BlockerKind.AUTHORIZED_ROUTE_SPACE_EXHAUSTED,
                current_discovery_ref="DISCOVERY-1",
                equivalent_routes_checked=True,
                route_attempts=(
                    RouteAttempt(
                        route_id="alternate-route",
                        succeeded=True,
                        readback_verified=True,
                        evidence_ref="RCP-ALT-1",
                    ),
                ),
            )
        )
        self.assertEqual(GateDecision.DENY_TERMINAL_CLAIM, decision.decision)
        self.assertIn("ROUTE_EXHAUSTION_CONTRADICTED_BY_VERIFIED_SUCCESS", decision.reason_codes)

    def test_safety_boundary_remains_hard_and_not_routed_around(self) -> None:
        decision = self.gate.evaluate(
            CapabilityDecisionRequest(
                objective="perform prohibited action",
                claim=TerminalClaim.CANNOT,
                scope=CapabilityScope.CURRENT_CHAT,
                state=CapabilityState.UNKNOWN,
                blocker=BlockerKind.SAFETY_OR_POLICY_HARD_BOUNDARY,
            )
        )
        self.assertEqual(GateDecision.ALLOW_BOUNDED, decision.decision)
        self.assertIn("safety", decision.allowed_language.lower())
        self.assertFalse(decision.manual_user_action_allowed)


if __name__ == "__main__":
    unittest.main()
