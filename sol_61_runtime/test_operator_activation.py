from __future__ import annotations

import unittest

from operator_activation import AppsScriptOAuthSpec, CloudRunCanarySpec, OperatorActivationPackage


class OperatorActivationPackageTests(unittest.TestCase):
    def test_cloud_run_manifest_and_fail_closed_promotion(self) -> None:
        spec = CloudRunCanarySpec(
            service="federation-omega-operator",
            region="us-central1",
            audience="https://example.run.app",
            endpoint="/canary",
            request_body={"operation": "ping"},
            expected_readback={"status": "ok"},
            rollback_operation="delete_canary",
        )
        manifest = OperatorActivationPackage.cloud_run_manifest(spec)
        self.assertFalse(manifest["truth_boundary"]["live_invocation_performed"])
        pending = OperatorActivationPackage.evaluate_promotion(manifest, {})
        self.assertEqual(pending["status"], "ACTIVATION_PENDING")
        receipts = {name: "verified" for name in manifest["required_receipts"]}
        live = OperatorActivationPackage.evaluate_promotion(manifest, receipts)
        self.assertEqual(live["status"], "LIVE_CERTIFIED")

    def test_apps_script_requires_human_oauth_and_native_receipts(self) -> None:
        spec = AppsScriptOAuthSpec(
            script_id="script-1",
            oauth_subject=None,
            required_scopes=OperatorActivationPackage.REQUIRED_SCOPES,
            standard_cloud_project_id="project-1",
            callback_uri="https://localhost/oauth/callback",
            state_nonce="nonce-1",
        )
        manifest = OperatorActivationPackage.apps_script_manifest(spec)
        self.assertFalse(manifest["authority_ready"])
        self.assertTrue(manifest["truth_boundary"]["owner_consent_required"])
        self.assertEqual(OperatorActivationPackage.evaluate_promotion(manifest, {})["status"], "ACTIVATION_PENDING")


if __name__ == "__main__":
    unittest.main()
