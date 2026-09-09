import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-provider-currentness-v1.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
WORKFLOW_PATH = ".github/workflows/fuse-mobile-provider-currentness-v1.yml"


class FuseMobileProviderCurrentnessV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_uses_existing_mobile_wif_identity_and_no_json_secret_auth(self) -> None:
        self.assertIn("id-token: write", self.text)
        self.assertIn(
            "projects/257649435135/locations/global/workloadIdentityPools/github-federation-omega/providers/github",
            self.text,
        )
        self.assertIn(
            "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            self.text,
        )
        self.assertIn("workload_identity_provider: ${{ env.WIF_PROVIDER }}", self.text)
        self.assertIn("service_account: ${{ env.READ_SA }}", self.text)
        self.assertNotIn("credentials_json:", self.text)
        self.assertNotIn("secrets.", self.text)

    def test_targets_exact_existing_mobile_gateway(self) -> None:
        self.assertIn("PROJECT_ID: sov-hybrid-suite", self.text)
        self.assertIn("PROJECT_NUMBER: '257649435135'", self.text)
        self.assertIn("REGION: africa-south1", self.text)
        self.assertIn("SERVICE: fuse-mobile-gateway", self.text)

    def test_provider_commands_are_read_only(self) -> None:
        required = (
            'gcloud run services describe "$SERVICE"',
            'gcloud run services get-iam-policy "$SERVICE"',
            "gcloud iap settings get",
            "gcloud iap web get-iam-policy",
        )
        for fragment in required:
            self.assertIn(fragment, self.text)

        forbidden = (
            "gcloud run deploy",
            "gcloud run services update",
            "gcloud run services delete",
            "gcloud run services add-iam-policy-binding",
            "gcloud run services set-iam-policy",
            "gcloud iap web add-iam-policy-binding",
            "gcloud iap web set-iam-policy",
            "gcloud secrets",
            "gcloud builds submit",
            "docker push",
            "artifactregistry.writer",
            "allow-unauthenticated",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, self.text)

    def test_never_invokes_gateway_or_model(self) -> None:
        forbidden = (
            "curl ",
            "wget ",
            "generateContent",
            "aiplatform",
            "generativelanguage",
            "GEMINI_API_KEY",
            "VERTEX_MODEL",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, self.text)
        self.assertIn("'service_invocation_performed': False", self.text)
        self.assertIn("'model_inference_performed': False", self.text)

    def test_receipt_fails_closed_and_redacts_identity_material(self) -> None:
        self.assertIn("WIF_AUTH_FAILED", self.text)
        self.assertIn("PROVIDER_READBACK_PARTIAL_OR_DENIED", self.text)
        self.assertIn("PROVIDER_READBACK_VERIFIED", self.text)
        self.assertIn("workload_identity_provider_sha256", self.text)
        self.assertIn("service_account_sha256", self.text)
        self.assertIn("'credential_value_recorded': False", self.text)
        self.assertIn("'provider_mutation_performed': False", self.text)
        self.assertIn("'iam_mutation_performed': False", self.text)
        self.assertIn("'oauth_mutation_performed': False", self.text)
        self.assertIn("'secret_read_or_mutation_performed': False", self.text)
        self.assertIn("'traffic_change_performed': False", self.text)

    def test_captures_private_ingress_and_iap_contract(self) -> None:
        self.assertIn("public_invoker_present", self.text)
        self.assertIn("iap_enabled", self.text)
        self.assertIn("ingress", self.text)
        self.assertIn("invoker_iam_disabled", self.text)
        self.assertIn("programmatic_client_count", self.text)
        self.assertIn("oauth_resource_client_id_present", self.text)
        self.assertIn("iap_policy_binding_count", self.text)

    def test_actions_are_pinned_and_checkout_drops_write_credentials(self) -> None:
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", self.text)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.text)
        self.assertIn("google-github-actions/setup-gcloud@e427ad8a34f8676edf47cf7d7925499adf3eb74f", self.text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_push_scope_is_only_this_court(self) -> None:
        self.assertIn('".github/workflows/fuse-mobile-provider-currentness-v1.yml"', self.text)
        self.assertIn('"tests/test_fuse_mobile_provider_currentness_v1.py"', self.text)
        self.assertNotIn("issues:", self.text)

    def test_airlock_binding_is_read_only_and_exact(self) -> None:
        self.assertIn(WORKFLOW_PATH, self.policy["active_workflow_allowlist"])
        self.assertEqual(
            ["push", "workflow_dispatch"],
            self.policy["allowed_events"][WORKFLOW_PATH],
        )
        self.assertEqual(["main"], self.policy["required_push_branches"][WORKFLOW_PATH])
        self.assertIn(WORKFLOW_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, self.policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(WORKFLOW_PATH, self.policy["provider_mutation_workflow_allowlist"])


if __name__ == "__main__":
    unittest.main()
