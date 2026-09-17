from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "federation-respawn-private-canary-v1.yml"


class RespawnPrivateCanaryWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_exact_owner_gated_dispatch(self) -> None:
        self.assertIn("[FO-DISPATCH] FEDERATION_RESPAWN_PRIVATE_CANARY_V1", self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)

    def test_repository_and_provider_permissions_are_bounded(self) -> None:
        self.assertIn("contents: read", self.text)
        self.assertIn("issues: read", self.text)
        self.assertIn("id-token: write", self.text)
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("issues: write", self.text)
        self.assertNotIn("pull-requests: write", self.text)
        self.assertNotIn("gcloud projects add-iam-policy-binding", self.text)
        self.assertNotIn("gcloud services enable", self.text)
        self.assertNotIn("secretmanager", self.text.lower())

    def test_private_provider_boundary_is_explicit(self) -> None:
        self.assertIn("--no-allow-unauthenticated", self.text)
        self.assertNotIn("--allow-unauthenticated", self.text.replace("--no-allow-unauthenticated", ""))
        self.assertIn("FEDERATION_PROVIDER_WRITES=false", self.text)
        self.assertIn("public_invocation':False", self.text)
        self.assertIn("iam_mutation_performed':False", self.text)

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
