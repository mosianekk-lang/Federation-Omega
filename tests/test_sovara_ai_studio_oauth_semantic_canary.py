from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"
REQUEST_PATH = ROOT / "governance/sovara_ai_studio_semantic_canary_request_v1.json"
POLICY_PATH = ROOT / "governance/github_airlock_policy.json"
SCRIPT_PATH = ROOT / "ops/sovara_ai_studio_semantic_canary.py"


class SovaraAIStudioSemanticCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW_PATH.exists():
            raise unittest.SkipTest("repository-only workflow contract is outside the Phoenix Core export")
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.script = SCRIPT_PATH.read_text(encoding="utf-8")
        cls.workflow_rel = ".github/workflows/sovara-ai-studio-semantic-canary.yml"

    def test_airlock_admits_bounded_read_only_workflow(self) -> None:
        self.assertIn(self.workflow_rel, self.policy["active_workflow_allowlist"])
        self.assertEqual(["push", "workflow_dispatch"], self.policy["allowed_events"][self.workflow_rel])
        self.assertEqual(["main"], self.policy["required_push_branches"][self.workflow_rel])
        self.assertIn(self.workflow_rel, self.policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(self.workflow_rel, self.policy["provider_mutation_workflow_allowlist"])

    def test_request_is_zero_case_data_and_zero_provider_mutation(self) -> None:
        self.assertTrue(self.request["execute"])
        self.assertEqual("GOOGLE_GEMINI_MULTI_ROUTE_CANARY", self.request["provider"])
        self.assertEqual("GOOGLE_WIF_SECRET_MANAGER_TRANSIENT_ACCESS", self.request["credential_mode"])
        self.assertEqual("gcp_secret_name:gemini-api-key", self.request["credential_reference"])
        self.assertEqual("gemini-api-key", self.request["credential_secret_name"])
        self.assertEqual("google_cloud", self.request["resolution_surface"])
        self.assertEqual(
            "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
            self.request["workload_identity_provider"],
        )
        self.assertEqual(
            "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            self.request["service_account"],
        )
        self.assertEqual(
            ["VERTEX_OAUTH_ADC", "DEVELOPER_API_SECRET_MANAGER"],
            self.request["preferred_execution_order"],
        )
        self.assertTrue(self.request["vertex_oauth_challenger"]["enabled"])
        self.assertEqual("global", self.request["vertex_oauth_challenger"]["location"])
        self.assertEqual(
            ["serviceusage.services.get", "serviceusage.services.use"],
            self.request["vertex_oauth_challenger"]["service_usage_permissions_required"],
        )
        self.assertEqual(
            ["aiplatform.publisherModels.get", "aiplatform.publisherModels.predict"],
            self.request["vertex_oauth_challenger"]["vertex_permissions_required"],
        )
        self.assertTrue(self.request["developer_api_secret_manager_fallback"]["enabled"])
        self.assertTrue(self.request["model_policy"]["discovery_required"])
        self.assertTrue(self.request["model_policy"]["allow_dynamic_fallback"])
        self.assertLessEqual(int(self.request["semantic_canary"]["max_output_tokens"]), 32)
        for key in (
            "case_data_allowed",
            "provider_mutation_allowed",
            "iam_mutation_allowed",
            "secret_mutation_allowed",
            "secret_value_logging_allowed",
            "deployment_allowed",
            "traffic_change_allowed",
            "external_communication_allowed",
        ):
            self.assertFalse(self.request[key], key)

    def test_workflow_reuses_existing_wif_and_runs_multi_route_helper(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.workflow)
        self.assertIn("google-github-actions/setup-gcloud@e427ad8a34f8676edf47cf7d7925499adf3eb74f", self.workflow)
        self.assertIn("workload_identity_provider: ${{ env.WIF_PROVIDER }}", self.workflow)
        self.assertIn("service_account: ${{ env.DEPLOYER_SA }}", self.workflow)
        self.assertIn("python3 ops/sovara_ai_studio_semantic_canary.py", self.workflow)
        self.assertNotIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", self.workflow)
        self.assertNotIn("credentials_json:", self.workflow)
        self.assertIn("Run Vertex OAuth challenger with Developer API fallback", self.workflow)

    def test_vertex_route_is_preferred_and_fallback_is_preserved(self) -> None:
        self.assertEqual("gemini-2.5-flash", self.request["vertex_oauth_challenger"]["preferred_models"][0])
        self.assertEqual("gemini-2.5-flash", self.request["model_policy"]["preferred_models"][0])
        self.assertIn("VERTEX_OAUTH_ADC", self.script)
        self.assertIn("DEVELOPER_API_SECRET_MANAGER", self.script)
        self.assertIn("SKIPPED_PREFERRED_ROUTE_VERIFIED", self.script)
        self.assertIn("SKIPPED_VERTEX_ROUTE_ATTEMPTED", self.script)
        self.assertIn("gcloud:auth:print-access-token", self.script)
        self.assertEqual(
            "gcp_secret_name:gemini-api-key",
            self.request["developer_api_secret_manager_fallback"]["credential_reference"],
        )

    def test_model_discovery_and_vertex_preflight_are_provider_readback_driven(self) -> None:
        self.assertIn("serviceusage.googleapis.com/v1/projects/", self.script)
        self.assertIn("aiplatform.googleapis.com", self.script)
        self.assertIn("publishers/google/models", self.script)
        self.assertIn(
            "aiplatform.publisherModels.predict",
            self.request["vertex_oauth_challenger"]["vertex_permissions_required"],
        )
        self.assertIn(
            "serviceusage.services.use",
            self.request["vertex_oauth_challenger"]["service_usage_permissions_required"],
        )
        self.assertIn("generativelanguage.googleapis.com/v1beta/models?", self.script)
        self.assertIn("PREFERRED_VERTEX_MODEL_READBACK", self.script)
        self.assertIn("PREFERRED_PROVIDER_DISCOVERED", self.script)
        self.assertIn("DYNAMIC_PROVIDER_DISCOVERY", self.script)

    def test_failure_paths_retain_redacted_provider_diagnostics(self) -> None:
        for token in (
            "AUTH_UNAVAILABLE",
            "VERTEX_SERVICEUSAGE_PERMISSION_HELD",
            "VERTEX_PERMISSION_HELD",
            "VERTEX_API_DISABLED",
            "VERTEX_MODEL_DISCOVERY_HELD",
            "CREDENTIAL_PERMISSION_UNAVAILABLE",
            "MODEL_DISCOVERY_HELD",
            "PROVIDER_SEMANTIC_HELD",
            "secret_access_error_sha256",
        ):
            self.assertIn(token, self.script)
        self.assertIn("AI_STUDIO_SEMANTIC_RECEIPT.json", self.workflow)
        self.assertIn("if-no-files-found: error", self.workflow)

    def test_semantic_promotion_requires_exact_nonce_and_provider_receipt(self) -> None:
        self.assertIn("text == nonce", self.script)
        self.assertIn('route["semantic_verified"] = status == 200 and text == nonce', self.script)
        self.assertIn('"provider_model_version": route_result.get("provider_model_version")', self.script)
        self.assertIn('"provider_request_id_or_equivalent": route_result.get("provider_request_id_or_equivalent")', self.script)
        self.assertIn('"nonce_sha256": route_result.get("nonce_sha256")', self.script)
        self.assertIn('route["response_text_sha256"] = _sha256_text(text) if text else None', self.script)
        self.assertIn('"provider_mutation_performed": False', self.script)
        self.assertIn('"selected_route"', self.script)

    def test_repository_write_credentials_are_disabled(self) -> None:
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertIn("id-token: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
