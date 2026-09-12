from __future__ import annotations

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "fuse-windows-relay-cloud-run-v1.yml"


class RelayWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_owner_only_default_deny_dispatch(self):
        self.assertIn("author_association == 'OWNER'", self.text)
        self.assertIn("[FO-DISPATCH] FUSE_WINDOWS_RELAY_CLOUD_RUN_V2", self.text)
        self.assertRegex(self.text, r"permissions:\n  contents: read\n  issues: read\n  id-token: write")
        self.assertIn("cancel-in-progress: false", self.text)

    def test_third_party_actions_are_sha_pinned(self):
        uses = re.findall(r"^\s*uses:\s*([^\s]+)", self.text, flags=re.MULTILINE)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40}$")
        self.assertIn("persist-credentials: false", self.text)

    def test_existing_service_keeps_tagged_zero_traffic_canary_and_rollback(self):
        self.assertIn("TAGGED_ZERO_TRAFFIC_EXISTING_SERVICE", self.text)
        self.assertIn("--no-traffic --tag relay-canary", self.text)
        self.assertIn("/healthz", self.text)
        self.assertIn("$CANARY_URL/mcp", self.text)
        self.assertIn("--to-revisions=\"$CANARY_REVISION=100\"", self.text)
        self.assertIn("if: failure() && env.PRODUCTION_SERVICE_PRESENT == 'true'", self.text)
        self.assertLess(self.text.index("$CANARY_URL/healthz"), self.text.index("$CANARY_REVISION=100"))

    def test_absent_service_uses_separate_isolated_canary_without_fake_zero_traffic(self):
        self.assertIn("ISOLATED_CANARY_SERVICE_WHEN_PRODUCTION_ABSENT", self.text)
        self.assertIn('TARGET_SERVICE="${SERVICE}-canary-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"', self.text)
        isolated_deploy = re.search(
            r'gcloud run deploy "\$TARGET_SERVICE"[^\n]+',
            self.text,
        )
        self.assertIsNotNone(isolated_deploy)
        self.assertNotIn("--no-traffic", isolated_deploy.group(0))
        self.assertIn("--min 0 --max 1", isolated_deploy.group(0))
        self.assertIn("PRODUCTION_SERVICE_UNEXPECTEDLY_CREATED", self.text)
        self.assertIn("PRODUCTION_ISOLATION_CHECKED=true", self.text)
        self.assertIn("CANARY_DELETE_POINTER=gcloud run services delete", self.text)
        self.assertIn('"production_isolation_checked": truth("PRODUCTION_ISOLATION_CHECKED")', self.text)
        self.assertIn('"canary_delete_pointer": os.environ.get("CANARY_DELETE_POINTER")', self.text)

    def test_promotion_cannot_target_isolated_first_service(self):
        self.assertIn(
            "if: env.ALLOW_PRODUCTION_PROMOTION == 'true' && env.PRODUCTION_SERVICE_PRESENT == 'true'",
            self.text,
        )
        self.assertIn("PRODUCTION_TRAFFIC_CHANGED=false", self.text)
        self.assertIn("PRODUCTION_TRAFFIC_CHANGED=true", self.text)
        self.assertIn('"production_traffic_changed": truth("PRODUCTION_TRAFFIC_CHANGED")', self.text)

    def test_agent_only_is_secret_manager_independent(self):
        self.assertIn("FUSE Windows Relay Cloud Run v2.4", self.text)
        self.assertIn("DEVICE_AUTH_MODE=ECDSA_P256_PUBLIC_KEY", self.text)
        self.assertIn('"secret_manager_required": False', self.text)
        self.assertNotIn("--set-secrets=", self.text)
        self.assertNotIn("gcloud secrets", self.text)
        self.assertNotIn("add-iam-policy-binding", self.text)
        self.assertNotIn("gcloud services enable", self.text)
        self.assertIn('"secret_value_recorded": False', self.text)
        self.assertIn("BROWSER_ENTRYPOINT_CHECKED=true", self.text)
        self.assertIn("MCP_FAIL_CLOSED_CHECKED=true", self.text)

    def test_receipt_binds_exact_source_provider_image_revision_and_topology(self):
        self.assertIn('"schema": "FUSE-WINDOWS-RELAY-DEPLOYMENT-RECEIPT-V26"', self.text)
        for field in (
            '"source_sha"',
            '"image_digest_uri"',
            '"canary_revision"',
            '"canary_url"',
            '"target_service"',
            '"deployment_topology"',
            '"production_service_present"',
        ):
            self.assertIn(field, self.text)


if __name__ == "__main__":
    unittest.main()
