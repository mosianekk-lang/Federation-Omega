from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "bubbles-provider-authority-recovery-probe.yml"
)
PROBE = ROOT / "ops" / "provider_authority_readonly_probe.py"


class ProviderAuthorityProbeContainmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")
        self.probe = PROBE.read_text(encoding="utf-8")

    def test_workflow_is_artifact_only_and_cannot_write_source(self) -> None:
        self.assertIn("contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertNotIn("git push", self.workflow)
        self.assertNotIn("git commit", self.workflow)
        self.assertNotIn("git add", self.workflow)

    def test_workflow_rejects_long_lived_key_file_routes(self) -> None:
        for forbidden in (
            "credentials_json:",
            "GCP_SA_KEY",
            "GCP_SERVICE_ACCOUNT_KEY",
            "GOOGLE_CREDENTIALS",
            "GOOGLE_SERVICE_ACCOUNT_KEY",
            "GCP_CREDENTIALS",
            "GOOGLE_GHA_CREDS_JSON",
            "GOOGLE_CLOUD_CREDENTIALS",
        ):
            self.assertNotIn(forbidden, self.workflow)

    def test_workflow_uses_only_wif_authentication_candidates(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("Try repository WIF binding", self.workflow)
        self.assertIn("Try canonical WIF binding", self.workflow)
        self.assertIn("workload_identity_provider:", self.workflow)
        self.assertIn("service_account:", self.workflow)

    def test_workflow_never_reads_secret_values(self) -> None:
        combined = f"{self.workflow}\n{self.probe}".lower()
        self.assertNotIn("secrets versions access", combined)
        self.assertNotIn("secretmanager.versions.access", combined)
        self.assertNotIn("fo_admin_token", combined)
        self.assertNotIn("archon_admin_token", combined)
        self.assertNotIn("authorization: bearer", combined)

    def test_runtime_receipt_is_uploaded_not_committed(self) -> None:
        self.assertIn("actions/upload-artifact@", self.workflow)
        self.assertIn(
            "provider-authority-output/receipt.json",
            self.workflow,
        )
        self.assertIn("source_write_attempted", self.workflow)
        self.assertIn("secret_values_accessed", self.workflow)

    def test_probe_has_no_provider_mutation_commands(self) -> None:
        lowered = self.probe.lower()
        for forbidden in (
            '"services",\n                    "enable"',
            '"service-accounts",\n                    "create"',
            '"run",\n                    "deploy"',
            '"secrets",\n                    "versions",\n                    "add"',
            "add-iam-policy-binding",
            "set-iam-policy",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_blocked_auth_is_a_failed_probe_not_a_green_success(self) -> None:
        self.assertIn("Enforce canonical provider proof", self.workflow)
        self.assertIn('if data["status"] != "VERIFIED"', self.workflow)
        self.assertIn("Provider authority remains blocked", self.workflow)

    def test_workflow_has_no_issue_open_trigger(self) -> None:
        self.assertNotIn("issues:", self.workflow)
        self.assertNotIn("types: [opened]", self.workflow)


if __name__ == "__main__":
    unittest.main()
