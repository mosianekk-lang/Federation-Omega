import unittest

from bubbles.control_plane import (
    ActionRequest,
    BubblesControlPlane,
    EffectClass,
    RouteKind,
)
from governance.external_action_firewall import LEASE_PROOF
from tests.test_external_action_firewall import ExternalActionFirewallTests  # noqa: F401


class BubblesControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.control = BubblesControlPlane()

    def test_native_drive_write_requires_connector_and_execution_lease_proof(self) -> None:
        request = ActionRequest(
            adapter_id="google_drive",
            action="update_document",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GOOGLE_WORKSPACE_CANONICAL_STORE",
            payload={"document_alias": "TEST_ONLY"},
        )
        blocked = self.control.decide(request)
        self.assertEqual(blocked.state, "CONSTRAINT")
        self.assertIn("connector_permission_verified", blocked.missing_proofs)
        self.assertIn(LEASE_PROOF, blocked.missing_proofs)

        still_blocked = self.control.decide(
            request,
            frozenset({"connector_permission_verified"}),
        )
        self.assertEqual(still_blocked.state, "CONSTRAINT")
        self.assertEqual(still_blocked.missing_proofs, (LEASE_PROOF,))

        ready = self.control.decide(
            request,
            frozenset({"connector_permission_verified", LEASE_PROOF}),
        )
        self.assertEqual(ready.state, "READY")
        self.assertEqual(ready.route_kind, RouteKind.CHATGPT_NATIVE)

    def test_cloud_write_fails_closed_without_provider_readback_contract(self) -> None:
        request = ActionRequest(
            adapter_id="google_cloud",
            action="run_harmless_canary",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GOOGLE_CLOUD_EXECUTION_PLANE",
        )
        decision = self.control.decide(
            request,
            frozenset(
                {
                    "provider_identity_verified",
                    "target_verified",
                    "action_scope_verified",
                    LEASE_PROOF,
                }
            ),
        )
        self.assertEqual(decision.state, "CONSTRAINT")
        self.assertEqual(decision.missing_proofs, ("provider_readback_contract",))

    def test_cloud_write_can_route_through_command_bus_when_all_gates_pass(self) -> None:
        request = ActionRequest(
            adapter_id="google_cloud",
            action="run_harmless_canary",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GOOGLE_CLOUD_EXECUTION_PLANE",
        )
        decision = self.control.decide(
            request,
            frozenset(
                {
                    "provider_identity_verified",
                    "target_verified",
                    "action_scope_verified",
                    "provider_readback_contract",
                    LEASE_PROOF,
                }
            ),
        )
        self.assertEqual(decision.state, "READY")
        self.assertEqual(decision.route_kind, RouteKind.GITHUB_COMMAND_BUS)

    def test_mcp_route_never_allows_write_on_current_surface(self) -> None:
        request = ActionRequest(
            adapter_id="bubbles_mcp",
            action="mutate_provider",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="ANY_PROVIDER",
        )
        decision = self.control.decide(request)
        self.assertEqual(decision.state, "CONSTRAINT")
        self.assertEqual(decision.route_kind, RouteKind.MCP_READ_ONLY)

    def test_secret_bearing_command_payload_is_rejected(self) -> None:
        request = ActionRequest(
            adapter_id="github",
            action="enqueue",
            effect=EffectClass.LOW_RISK_WRITE,
            target_alias="GITHUB_ACTIONS_A0_A1",
            payload={"api_key": "must-never-enter-command-bus"},
        )
        decision = self.control.decide(
            request,
            frozenset({"connector_permission_verified", LEASE_PROOF}),
        )
        self.assertEqual(decision.state, "CONSTRAINT")
        with self.assertRaises(ValueError):
            self.control.command_envelope(request)

    def test_command_envelope_is_deterministic_and_proof_safe(self) -> None:
        request = ActionRequest(
            adapter_id="apps_script",
            action="inspect_project",
            effect=EffectClass.READ,
            target_alias="GOOGLE_APPS_SCRIPT_AUTOMATION",
            payload={"project_alias": "CANARY_ONLY"},
        )
        first = self.control.command_envelope(request)
        second = self.control.command_envelope(request)
        self.assertEqual(first["command_sha256"], second["command_sha256"])
        self.assertIn("provider execution", first["truth_boundary"])


if __name__ == "__main__":
    unittest.main()
