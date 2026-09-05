from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"
REQUEST_PATH = ROOT / "governance/sovara_ai_studio_semantic_canary_request_v1.json"
POLICY_PATH = ROOT / "governance/github_airlock_policy.json"


class SovaraAIStudioAuthKeySemanticCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.workflow_rel = ".github/workflows/sovara-ai-studio-semantic-canary.yml"

    def test_airlock_admits_bounded_read_only_workflow(self) -> None:
        self.assertIn(self.workflow_rel, self.policy["active_workflow_allowlist"])
        self.assertEqual(["push", "workflow_dispatch"], self.policy["allowed_events"][self.workflow_rel])
        self.assertEqual(["main"], self.policy["required_push_branches"][self.workflow_rel])
        self.assertIn(self.workflow_rel, self.policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(self.workflow_rel, self.policy["provider_mutation_workflow_allowlist"])

    def test_request_is_zero_case_data_and_zero_provider_mutation(self) -> None:
        self.assertTrue(self.request["execute"])
        self.assertEqual("GEMINI_AUTHORIZATION_KEY_ENV_SECRET", self.request["credential_mode"])
        self.assertEqual("GITHUB_ACTIONS_SECRET:GEMINI_API_KEY", self.request["credential_reference"])
        self.assertEqual("GOOGLE_GEMINI_DEVELOPER_API", self.request["provider"])
        self.assertTrue(self.request["model_policy"]["discovery_required"])
        self.assertTrue(self.request["model_policy"]["allow_dynamic_fallback"])
        self.assertLessEqual(int(self.request["semantic_canary"]["max_output_tokens"]), 128)
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

    def test_workflow_uses_runtime_secret_not_wif_or_secret_manager(self) -> None:
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", self.workflow)
        self.assertIn("'x-goog-api-key':key", self.workflow)
        self.assertNotIn("google-github-actions/auth@", self.workflow)
        self.assertNotIn("gcloud secrets versions access", self.workflow)
        self.assertNotIn("Authorization: Bearer", self.workflow)
        self.assertNotIn("print(key)", self.workflow)
        self.assertNotIn("hashlib.sha256(key", self.workflow)
        self.assertIn("'credential_value_recorded':False", self.workflow)
        self.assertIn("'credential_value_hashed':False", self.workflow)

    def test_model_discovery_precedes_selection_and_has_dynamic_fallback(self) -> None:
        self.assertIn("generativelanguage.googleapis.com/v1beta/models?", self.workflow)
        self.assertIn("supportedGenerationMethods", self.workflow)
        self.assertIn("PREFERRED_PROVIDER_DISCOVERED", self.workflow)
        self.assertIn("DYNAMIC_PROVIDER_DISCOVERY", self.workflow)
        self.assertIn("MODEL_DISCOVERY_HELD", self.workflow)
        self.assertNotIn("MODEL: gemini-2.5-flash", self.workflow)

    def test_failure_paths_retain_redacted_provider_diagnostics(self) -> None:
        for token in (
            "CREDENTIAL_MISSING",
            "MODEL_DISCOVERY_HELD",
            "PROVIDER_SEMANTIC_HELD",
            "models_list_http_status",
            "generate_http_status",
            "provider_error_message_sha256",
            "AI_STUDIO_SEMANTIC_RECEIPT.json",
            "if-no-files-found: error",
        ):
            self.assertIn(token, self.workflow)
        self.assertNotIn("print(error_message)", self.workflow)

    def test_semantic_promotion_requires_exact_nonce_and_provider_receipt(self) -> None:
        self.assertIn("exact=generate_status==200 and text==expected", self.workflow)
        self.assertIn("'semantic_verified':exact", self.workflow)
        self.assertIn("'provider_model_version'", self.workflow)
        self.assertIn("'provider_request_id_or_equivalent'", self.workflow)
        self.assertIn("'nonce_sha256'", self.workflow)
        self.assertIn("'response_text_sha256'", self.workflow)
        self.assertIn("'provider_mutation_performed':False", self.workflow)

    def test_repository_write_credentials_are_disabled(self) -> None:
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("id-token: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
