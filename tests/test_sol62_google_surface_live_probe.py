from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sol62-google-surface-probe.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"


class Sol62GoogleSurfaceLiveProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW.exists():
            raise unittest.SkipTest(
                "workflow-free export excludes repository workflow controls"
            )
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_probe_is_admitted_but_has_no_cloud_mutation_authority(self) -> None:
        workflow = ".github/workflows/sol62-google-surface-probe.yml"
        self.assertIn(workflow, self.policy["active_workflow_allowlist"])
        self.assertEqual(["push", "workflow_dispatch"], self.policy["allowed_events"][workflow])
        self.assertEqual(["main"], self.policy["required_push_branches"][workflow])
        self.assertIn(workflow, self.policy["execution_quarantine"]["keep_active"])
        self.assertNotIn(workflow, self.policy["oidc_workflow_allowlist"])
        self.assertNotIn(workflow, self.policy["provider_mutation_workflow_allowlist"])
        self.assertNotIn("id-token: write", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("persist-credentials: false", self.text)
        for forbidden in (
            "gcloud iap settings set",
            "gcloud iap web add-iam-policy-binding",
            "gcloud iap web remove-iam-policy-binding",
            "gcloud run services update",
            "gcloud run deploy",
            "gcloud secrets versions access",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_apps_script_probe_is_exact_read_only_provider_readback(self) -> None:
        self.assertIn("bubbles/apps_script_deployment_probe.py", self.text)
        self.assertIn("--receipt /tmp/sol62-google/SURFACE_RECEIPT.json", self.text)
        self.assertIn("provider_mutation_performed\":false", self.text)
        self.assertIn("credential_values_recorded\":false", self.text)

    def test_cloud_iap_probe_reuses_existing_credentials_and_records_only_redacted_state(self) -> None:
        self.assertIn("HAS_GCP_READ_CREDENTIAL", self.text)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.text)
        self.assertIn("credentials_json: ${{ secrets.GCP_SA_KEY ||", self.text)
        self.assertIn("gcloud run services describe", self.text)
        self.assertIn("gcloud iap settings get", self.text)
        self.assertIn("--resource-type=cloud-run", self.text)
        self.assertIn("gcloud iap web get-iam-policy", self.text)
        self.assertIn("oauth_resource_client_id_sha256", self.text)
        self.assertIn("programmatic_client_sha256", self.text)
        self.assertIn("member_sha256", self.text)
        self.assertIn("oauth_client_secret_recorded':False", self.text)
        self.assertIn("provider_mutation_performed':False", self.text)
        self.assertIn("iam_mutation_performed':False", self.text)
        self.assertIn("oauth_mutation_performed':False", self.text)
        self.assertIn("traffic_change_performed':False", self.text)
        self.assertNotIn("clientSecret':", self.text)
        self.assertNotIn("oauth2_client_secret", self.text)

    def test_ai_studio_canary_never_logs_or_persists_key(self) -> None:
        self.assertIn("HAS_GEMINI_API_KEY", self.text)
        self.assertIn("secrets.GEMINI_API_KEY", self.text)
        self.assertIn("set +x", self.text)
        self.assertIn("x-goog-api-key", self.text)
        self.assertIn("CREDENTIAL_MISSING", self.text)
        self.assertIn("SEMANTIC_MISMATCH", self.text)
        self.assertIn("VERIFIED_SCOPED", self.text)
        self.assertNotIn("echo $GEMINI_API_KEY", self.text)
        self.assertNotIn("print(key)", self.text)

    def test_read_failure_is_evidence_not_a_provider_effect(self) -> None:
        self.assertIn("AUTH_CREDENTIAL_MISSING", self.text)
        self.assertIn("PROVIDER_READBACK_PARTIAL_OR_DENIED", self.text)
        self.assertIn("PROVIDER_READBACK_VERIFIED", self.text)
        self.assertIn("service_error_sha256", self.text)
        self.assertIn("settings_error_sha256", self.text)
        self.assertIn("policy_error_sha256", self.text)


if __name__ == "__main__":
    unittest.main()
