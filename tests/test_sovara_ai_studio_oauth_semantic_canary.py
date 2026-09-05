from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"
REQUEST_PATH = ROOT / "governance/sovara_ai_studio_semantic_canary_request_v1.json"
POLICY_PATH = ROOT / "governance/github_airlock_policy.json"


class SovaraAIStudioOAuthSemanticCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW_PATH.exists():
            raise unittest.SkipTest("repository-only workflow contract is outside the Phoenix Core export")
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.workflow_rel = ".github/workflows/sovara-ai-studio-semantic-canary.yml"

    def test_airlock_exactly_admits_bounded_oidc_workflow(self) -> None:
        self.assertIn(self.workflow_rel, self.policy["active_workflow_allowlist"])
        self.assertIn(self.workflow_rel, self.policy["oidc_workflow_allowlist"])
        self.assertEqual(["push", "workflow_dispatch"], self.policy["allowed_events"][self.workflow_rel])
        self.assertEqual(["main"], self.policy["required_push_branches"][self.workflow_rel])
        self.assertIn(self.workflow_rel, self.policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(self.workflow_rel, self.policy["provider_mutation_workflow_allowlist"])

    def test_request_is_zero_case_data_and_zero_provider_mutation(self) -> None:
        self.assertTrue(self.request["execute"])
        self.assertEqual("GOOGLE_OAUTH2_WIF_ACCESS_TOKEN", self.request["credential_mode"])
        self.assertEqual("GOOGLE_GEMINI_DEVELOPER_API", self.request["provider"])
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

    def test_workflow_uses_keyless_scoped_oauth_not_api_key_or_secret_access(self) -> None:
        self.assertIn("token_format: access_token", self.workflow)
        self.assertIn("https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/generative-language.retriever", self.workflow)
        self.assertIn("steps.google_auth.outputs.access_token", self.workflow)
        self.assertIn("Authorization: Bearer $ACCESS_TOKEN", self.workflow)
        self.assertIn("x-goog-user-project: $PROJECT_ID", self.workflow)
        self.assertIn("generativelanguage.googleapis.com/v1/models", self.workflow)
        self.assertIn("generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent", self.workflow)
        self.assertNotIn("gcloud secrets versions access", self.workflow)
        self.assertNotIn("x-goog-api-key", self.workflow)
        self.assertNotIn("GEMINI_API_KEY", self.workflow)
        self.assertNotIn("SECRET_ID", self.workflow)

    def test_failure_path_retains_redacted_provider_diagnostics(self) -> None:
        self.assertIn("models_list_http_status", self.workflow)
        self.assertIn("generate_http_status", self.workflow)
        self.assertIn("provider_error_message_sha256", self.workflow)
        self.assertIn("provider_error_reasons", self.workflow)
        self.assertIn("AI_STUDIO_SEMANTIC_RECEIPT.json", self.workflow)
        self.assertIn("if-no-files-found: error", self.workflow)
        self.assertNotIn("print(error_message)", self.workflow)

    def test_semantic_promotion_requires_exact_nonce_and_redacted_receipt(self) -> None:
        self.assertIn("exact=(generate_status==200 and text==nonce)", self.workflow)
        self.assertIn("'semantic_verified':exact", self.workflow)
        self.assertIn("'credential_value_recorded':False", self.workflow)
        self.assertIn("'secret_value_recorded':False", self.workflow)
        self.assertIn("'case_data_processed':False", self.workflow)
        self.assertIn("'provider_mutation_performed':False", self.workflow)
        self.assertIn("PROVIDER_SEMANTIC_HELD", self.workflow)

    def test_repository_write_credentials_are_disabled(self) -> None:
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertIn("id-token: write", self.workflow)
        self.assertNotIn("contents: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
