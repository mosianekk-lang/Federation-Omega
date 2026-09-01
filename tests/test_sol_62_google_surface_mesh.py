from __future__ import annotations

import unittest

from sol_61_runtime.sol_62_google_surface_mesh import (
    NoVerifiedRoute,
    Operation,
    load_google_surface_mesh,
)


class Sol62GoogleSurfaceMeshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mesh = load_google_surface_mesh()

    def test_apps_script_queue_runtime_is_primary_verified_route(self) -> None:
        decision = self.mesh.route(Operation.APPS_SCRIPT_SAFE_COMMAND, command="verify_state")
        self.assertTrue(decision.executable)
        self.assertEqual(decision.surface, "GOOGLE_APPS_SCRIPT_QUEUE_RUNTIME")
        self.assertEqual(decision.state, "OPERATIONAL_VERIFIED_SCOPED")
        canary = self.mesh.surfaces[decision.surface]["provider_canary"]
        self.assertEqual(canary["command_id"], "SOL62-GAS-VERIFY-20260901T042649Z")
        self.assertEqual(canary["status"], "EXECUTED")
        self.assertEqual(canary["provider_state"], "verified_live")
        self.assertEqual(canary["verification_queue_state"], "verified_live")

    def test_apps_script_unverified_command_is_fail_closed(self) -> None:
        with self.assertRaises(NoVerifiedRoute):
            self.mesh.route(Operation.APPS_SCRIPT_SAFE_COMMAND, command="delete_everything")

    def test_stale_apps_script_web_app_never_inherits_queue_maturity(self) -> None:
        web = self.mesh.surfaces["GOOGLE_APPS_SCRIPT_WEB_APP"]
        queue = self.mesh.surfaces["GOOGLE_APPS_SCRIPT_QUEUE_RUNTIME"]
        self.assertEqual(queue["state"], "OPERATIONAL_VERIFIED_SCOPED")
        self.assertEqual(web["last_probe_http_status"], 404)
        self.assertEqual(web["automation_level"], "DO_NOT_ROUTE")
        self.assertNotEqual(web["state"], queue["state"])

    def test_google_cloud_read_is_available_but_mutation_is_held(self) -> None:
        read = self.mesh.route(Operation.GOOGLE_CLOUD_READ)
        self.assertTrue(read.executable)
        self.assertEqual(read.surface, "GOOGLE_CLOUD_WIF_CONTROL_PLANE")
        cloud = self.mesh.surfaces[read.surface]
        self.assertTrue(cloud["oidc_exchange_verified"])
        self.assertTrue(cloud["adc_runtime_identity_verified"])
        self.assertFalse(cloud["wif_hardened_contract_verified"])
        self.assertEqual(cloud["blocking_provider_permission"], "iam.workloadIdentityPoolProviders.update")
        self.assertEqual(cloud["alternate_github_admin_credential_aliases_verified"], 0)
        with self.assertRaisesRegex(NoVerifiedRoute, "hardened WIF"):
            self.mesh.route(Operation.GOOGLE_CLOUD_MUTATION)

    def test_apps_script_source_control_does_not_inherit_daemon_authority(self) -> None:
        source = self.mesh.surfaces["GOOGLE_APPS_SCRIPT_SOURCE_CONTROL"]
        self.assertEqual(source["state"], "OWNER_OAUTH_REQUIRED")
        self.assertFalse(source["service_accounts_sufficient"])
        with self.assertRaisesRegex(NoVerifiedRoute, "human OAuth"):
            self.mesh.route(Operation.APPS_SCRIPT_SOURCE_MUTATION)

    def test_gemini_inference_does_not_inherit_paid_profile_or_cloud_identity(self) -> None:
        vertex = self.mesh.surfaces["GEMINI_VERTEX"]
        ai_studio = self.mesh.surfaces["GEMINI_AI_STUDIO_DEVELOPER_API"]
        self.assertFalse(vertex["provider_native_inference_verified"])
        self.assertEqual(ai_studio["state"], "CREDENTIAL_MISSING_ON_SOL_EXECUTION_PLANE")
        self.assertFalse(ai_studio["credential_value_recorded"])
        self.assertFalse(ai_studio["last_semantic_verified"])
        with self.assertRaisesRegex(NoVerifiedRoute, "Gemini inference held"):
            self.mesh.route(Operation.GEMINI_INFERENCE)

    def test_automation_plan_separates_executable_and_blocked_lanes(self) -> None:
        plan = self.mesh.automation_plan()
        executable = {item["operation"] for item in plan["executable"]}
        blocked = {item["operation"] for item in plan["blocked"]}
        self.assertEqual(
            executable,
            {Operation.APPS_SCRIPT_SAFE_COMMAND.value, Operation.GOOGLE_CLOUD_READ.value},
        )
        self.assertEqual(
            blocked,
            {
                Operation.APPS_SCRIPT_SOURCE_MUTATION.value,
                Operation.GOOGLE_CLOUD_MUTATION.value,
                Operation.GEMINI_INFERENCE.value,
            },
        )
        self.assertTrue(plan["no_cross_surface_maturity_inheritance"])


if __name__ == "__main__":
    unittest.main()
