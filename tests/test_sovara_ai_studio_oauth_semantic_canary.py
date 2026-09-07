from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"
REQUEST_PATH = ROOT / "governance/sovara_ai_studio_semantic_canary_request_v1.json"
POLICY_PATH = ROOT / "governance/github_airlock_policy.json"
SCRIPT_PATH = ROOT / "ops/sovara_ai_studio_semantic_canary.py"


class SovaraAIStudioAuthKeySemanticCanaryTests(unittest.TestCase):
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
        self.assertEqual("GOOGLE_GEMINI_DEVELOPER_API", self.request["provider"])
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

    def test_workflow_reuses_existing_wif_and_secret_manager_route(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.workflow)
        self.assertIn("google-github-actions/setup-gcloud@e427ad8a34f8676edf47cf7d7925499adf3eb74f", self.workflow)
        self.assertIn("workload_identity_provider: ${{ env.WIF_PROVIDER }}", self.workflow)
        self.assertIn("service_account: ${{ env.DEPLOYER_SA }}", self.workflow)
        self.assertIn("python3 ops/sovara_ai_studio_semantic_canary.py", self.workflow)
        self.assertNotIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", self.workflow)
        self.assertNotIn("credentials_json:", self.workflow)
        self.assertNotIn("Authorization: Bearer", self.workflow)

    def test_model_discovery_precedes_selection_and_has_dynamic_fallback(self) -> None:
        self.assertEqual("gemini-2.5-flash", self.request["model_policy"]["preferred_models"][0])
        self.assertIn("allow_dynamic_fallback", self.workflow)
        self.assertIn("generativelanguage.googleapis.com/v1beta/models?", self.script)
        self.assertIn("PREFERRED_PROVIDER_DISCOVERED", self.script)
        self.assertIn("DYNAMIC_PROVIDER_DISCOVERY", self.script)

    def test_failure_paths_retain_redacted_provider_diagnostics(self) -> None:
        for token in (
            "AUTH_UNAVAILABLE",
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
        self.assertIn('"semantic_verified": exact', self.script)
        self.assertIn('"provider_model_version": body.get("modelVersion")', self.script)
        self.assertIn('"provider_request_id_or_equivalent": request_id', self.script)
        self.assertIn('"nonce_sha256": _sha256_text(nonce)', self.script)
        self.assertIn('"response_text_sha256": _sha256_text(text)', self.script)
        self.assertIn('"provider_mutation_performed": False', self.script)

    def test_repository_write_credentials_are_disabled(self) -> None:
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertIn("id-token: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
