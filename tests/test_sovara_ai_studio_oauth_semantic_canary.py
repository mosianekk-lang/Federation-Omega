from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/sovara-ai-studio-semantic-canary.yml"
REQUEST_PATH = ROOT / "governance/sovara_ai_studio_semantic_canary_request_v1.json"
POLICY_PATH = ROOT / "governance/github_airlock_policy.json"


class SovaraAIStudioDualRouteSemanticCanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW_PATH.exists():
            raise unittest.SkipTest("repository-only workflow contract is outside the Phoenix Core export")
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.workflow_rel = ".github/workflows/sovara-ai-studio-semantic-canary.yml"

    def test_airlock_admits_existing_semantic_workflow_and_oidc(self) -> None:
        self.assertIn(self.workflow_rel, self.policy["active_workflow_allowlist"])
        self.assertEqual(["push", "workflow_dispatch"], self.policy["allowed_events"][self.workflow_rel])
        self.assertEqual(["main"], self.policy["required_push_branches"][self.workflow_rel])
        self.assertIn(self.workflow_rel, self.policy["execution_quarantine"]["keep_active"])
        self.assertIn(self.workflow_rel, self.policy["oidc_workflow_allowlist"])
        self.assertNotIn(self.workflow_rel, self.policy["provider_mutation_workflow_allowlist"])

    def test_request_is_zero_private_data_and_zero_provider_mutation(self) -> None:
        self.assertTrue(self.request["execute"])
        self.assertEqual("GEMINI_AUTHORIZATION_KEY_ENV_SECRET", self.request["credential_mode"])
        self.assertEqual("GITHUB_ACTIONS_SECRET:GEMINI_API_KEY", self.request["credential_reference"])
        fallback = self.request["fallback_route"]
        self.assertTrue(fallback["enabled"])
        self.assertEqual("GOOGLE_VERTEX_AI", fallback["provider"])
        self.assertEqual("GITHUB_WIF_ADC", fallback["credential_mode"])
        self.assertEqual("gemini-2.5-flash", fallback["model"])
        self.assertEqual("global", fallback["location"])
        self.assertEqual("aiplatform.endpoints.predict", fallback["required_permission"])
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

    def test_developer_api_route_is_preserved_without_secret_disclosure(self) -> None:
        for token in (
            "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}",
            "'x-goog-api-key':key",
            "generativelanguage.googleapis.com/v1beta/models?",
            "supportedGenerationMethods",
            "MODEL_DISCOVERY_HELD",
        ):
            self.assertIn(token, self.workflow)
        self.assertNotIn("print(key)", self.workflow)
        self.assertNotIn("hashlib.sha256(key", self.workflow)
        self.assertIn("'credential_value_recorded':False", self.workflow)
        self.assertIn("'credential_value_hashed':False", self.workflow)

    def test_wif_vertex_fallback_is_exact_and_permission_gated(self) -> None:
        for token in (
            "id-token: write",
            "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093",
            "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
            "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            "cloudresourcemanager.googleapis.com/v1/projects/{project}:testIamPermissions",
            "aiplatform.endpoints.predict",
            "https://aiplatform.googleapis.com",
            "publishers/google/models/{model}:generateContent",
        ):
            self.assertIn(token, self.workflow)
        self.assertIn("if not permission_ok:", self.workflow)
        self.assertIn("no inference attempted", self.workflow)

    def test_semantic_promotion_requires_exact_nonce_and_provider_receipt(self) -> None:
        self.assertIn("exact=status==200 and text==expected", self.workflow)
        for token in (
            "'semantic_verified':exact",
            "'provider_model_version':model_version",
            "'provider_request_id_or_equivalent':request_id",
            "'nonce_sha256'",
            "'response_text_sha256'",
            "'usage_metadata'",
        ):
            self.assertIn(token, self.workflow)

    def test_repository_write_credentials_are_disabled_and_no_provider_mutation_commands_exist(self) -> None:
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        for bad in (
            "gcloud services enable",
            "add-iam-policy-binding",
            "remove-iam-policy-binding",
            "gcloud run deploy",
            "gcloud run services update",
            "gcloud run services update-traffic",
            "gcloud secrets versions access",
            "git push",
            "git commit",
        ):
            self.assertNotIn(bad, self.workflow)

    def test_all_actions_are_immutable_sha_pinned(self) -> None:
        refs = re.findall(r"uses:\s*([^\s]+)", self.workflow)
        self.assertTrue(refs)
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}$", r) for r in refs), refs)


if __name__ == "__main__":
    unittest.main()
