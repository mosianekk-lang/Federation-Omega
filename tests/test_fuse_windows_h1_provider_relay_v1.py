from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/fuse-windows-h1-provider-relay-v1.yml"


class FuseWindowsH1ProviderRelayWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_exact_owner_dispatch_contract(self):
        self.assertIn("[FO-DISPATCH] FUSE_WINDOWS_H1_PROVIDER_RELAY_V1", self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)

    def test_keyless_provider_identity_is_pinned(self):
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.text)
        self.assertIn("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com", self.text)
        self.assertIn("superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com", self.text)

    def test_no_host_credential_copy_or_container_mount(self):
        forbidden = [
            "--volume $GOOGLE_APPLICATION_CREDENTIALS",
            "--volume \"$GOOGLE_APPLICATION_CREDENTIALS",
            "cp $GOOGLE_APPLICATION_CREDENTIALS",
            "cp \"$GOOGLE_APPLICATION_CREDENTIALS",
            "cat $GOOGLE_APPLICATION_CREDENTIALS",
            "cat \"$GOOGLE_APPLICATION_CREDENTIALS",
            "docker run --detach",
        ]
        for token in forbidden:
            self.assertNotIn(token, self.text)

    def test_pairing_epochs_are_bound_at_provider_runtime(self):
        self.assertIn("FUSE_WINDOWS_SOURCE_EPOCH=$GITHUB_SHA", self.text)
        self.assertIn("FUSE_WINDOWS_POLICY_EPOCH=$WINDOWS_POLICY_EPOCH", self.text)
        self.assertIn("FUSE_WINDOWS_H1_TPM_PAIRING_V1", self.text)

    def test_provider_relay_is_bounded_lightweight(self):
        for required in ["--cpu 1", "--memory 512Mi", "--min 0", "--max 1", "--concurrency 20"]:
            self.assertIn(required, self.text)
        self.assertIn("'gcp_heavy_compute':'DENY'", self.text)
        self.assertIn("'heavy_compute_performed':False", self.text)

    def test_semantic_and_fail_closed_courts_are_required(self):
        self.assertIn("$SERVICE_URL/healthz", self.text)
        self.assertIn("$SERVICE_URL/node", self.text)
        self.assertIn("$SERVICE_URL/mcp", self.text)
        self.assertIn("$SERVICE_URL/agent/enroll/start", self.text)
        self.assertIn("MCP_FAIL_CLOSED_REQUIRED", self.text)
        self.assertIn("PAIR_ROUTE_FAIL_CLOSED_REQUIRED", self.text)
        self.assertIn("RELAY_PROVIDER_VERIFIED=true", self.text)

    def test_rollback_pointer_and_no_production_claim(self):
        self.assertIn("gcloud run services delete", self.text)
        self.assertIn("'production_traffic_changed':False", self.text)
        self.assertIn("secret_value_recorded", self.text)


if __name__ == "__main__":
    unittest.main()
