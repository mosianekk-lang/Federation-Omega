import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/federation-respawn-private-canary-v1.yml"
WORKFLOW = ROOT / WORKFLOW_PATH
POLICY = ROOT / "governance" / "github_airlock_policy.json"
TITLE = "[FO-DISPATCH] FEDERATION_RESPAWN_PRIVATE_CANARY_V1"
UPLOAD_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"


class RespawnPrivateCanaryWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW.exists():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_exact_owner_gated_dispatch(self) -> None:
        self.assertIn(TITLE, self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)

    def test_airlock_lease_is_exact_and_bounded(self) -> None:
        self.assertIn(WORKFLOW_PATH, self.policy["active_workflow_allowlist"])
        self.assertEqual(self.policy["allowed_events"][WORKFLOW_PATH], ["issues"])
        self.assertIn(WORKFLOW_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, self.policy["provider_mutation_workflow_allowlist"])
        self.assertEqual(self.policy["provider_mutation_exact_issue_titles"][WORKFLOW_PATH], TITLE)
        self.assertIn(WORKFLOW_PATH, self.policy["execution_quarantine"]["keep_active"])
        required = set(self.policy["provider_mutation_required_markers"][WORKFLOW_PATH])
        self.assertTrue({
            "--no-allow-unauthenticated",
            "public_invocation",
            "provider_mutation_performed",
            "FEDERATION_PROVIDER_WRITES=false",
            "google_workspace_provider_readback",
        }.issubset(required))
        forbidden = set(self.policy["provider_mutation_forbidden_markers"][WORKFLOW_PATH])
        self.assertIn("gcloud projects add-iam-policy-binding", forbidden)
        self.assertIn("gcloud services enable", forbidden)
        self.assertIn("gcloud secrets versions access", forbidden)

    def test_repository_and_provider_permissions_are_bounded(self) -> None:
        self.assertIn("contents: read", self.text)
        self.assertIn("issues: read", self.text)
        self.assertIn("id-token: write", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("issues: write", self.text)
        self.assertNotIn("pull-requests: write", self.text)
        self.assertNotIn("gcloud projects add-iam-policy-binding", self.text)
        self.assertNotIn("gcloud run services add-iam-policy-binding", self.text)
        self.assertNotIn("gcloud services enable", self.text)
        self.assertNotIn("secretmanager", self.text.lower())

    def test_external_actions_are_immutable(self) -> None:
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", self.text)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.text)
        self.assertIn("google-github-actions/setup-gcloud@e427ad8a34f8676edf47cf7d7925499adf3eb74f", self.text)
        self.assertIn(f"actions/upload-artifact@{UPLOAD_SHA}", self.text)
        self.assertNotIn("actions/upload-artifact@v4", self.text)

    def test_private_provider_boundary_is_explicit(self) -> None:
        self.assertIn("--no-allow-unauthenticated", self.text)
        self.assertNotIn("--allow-unauthenticated", self.text.replace("--no-allow-unauthenticated", ""))
        self.assertIn("FEDERATION_PROVIDER_WRITES=false", self.text)
        self.assertIn("public_invocation':False", self.text)
        self.assertIn("iam_mutation_performed':False", self.text)
        self.assertIn("existing service IAM changed during canary", self.text)

    def test_cloud_run_tag_invocation_uses_canonical_service_audience(self) -> None:
        self.assertIn("service_url=$SERVICE_URL", self.text)
        self.assertIn("canary_url=$CANARY_URL", self.text)
        self.assertIn("id_token_audience: ${{ steps.endpoint.outputs.service_url }}", self.text)
        self.assertIn("CANARY_URL: ${{ steps.endpoint.outputs.canary_url }}", self.text)
        self.assertNotIn("id_token_audience: ${{ steps.endpoint.outputs.canary_url }}", self.text)

    def test_provider_object_id_is_runtime_configuration_not_source_constant(self) -> None:
        self.assertIn("vars.FEDERATION_SYNC_BUS_SHEET_ID", self.text)
        self.assertNotIn("1N9plg1P3lY0_0w2kWc4WHIH-rqK62Xq1tU5WRYtCWfo", self.text)

    def test_canary_proves_chatgpt_native_read_contract(self) -> None:
        for tool in (
            "bootstrap_spawn",
            "already_solved",
            "get_current_federation_state",
            "resume_federation_mission",
            "get_federation_corpus_coverage",
            "search",
            "fetch",
            "federation_health",
        ):
            self.assertIn(tool, self.text)
        self.assertIn("FUSE_CHATGPT_THIN_SHIM_V1", self.text)
        self.assertIn("google_workspace_provider_readback", self.text)
        self.assertIn("full_account_history_proven", self.text)

    def test_existing_service_candidate_does_not_take_existing_traffic(self) -> None:
        self.assertIn("--no-traffic", self.text)
        self.assertIn("new_percent == 0", self.text)
        self.assertIn("pre_existing_traffic_preserved", self.text)


if __name__ == "__main__":
    unittest.main()
