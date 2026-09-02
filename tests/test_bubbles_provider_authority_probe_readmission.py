import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "bubbles-provider-authority-recovery-probe.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
PATH = ".github/workflows/bubbles-provider-authority-recovery-probe.yml"


class ProviderAuthorityProbeReadmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not WORKFLOW.exists():
            raise unittest.SkipTest(
                "workflow-free Phoenix Core export intentionally excludes repository workflow controls"
            )
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_probe_is_active_with_exact_safe_events(self):
        self.assertIn(PATH, self.policy["active_workflow_allowlist"])
        self.assertEqual(self.policy["allowed_events"][PATH], ["issues", "workflow_dispatch"])
        self.assertIn(PATH, self.policy["execution_quarantine"]["keep_active"])
        self.assertIn(PATH, self.policy["oidc_workflow_allowlist"])

    def test_probe_is_read_only_and_artifact_backed(self):
        self.assertIn("contents: read", self.workflow)
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertNotIn("git push", self.workflow)
        self.assertNotIn("git commit", self.workflow)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", self.workflow)
        self.assertIn("provider-authority-output/receipt.json", self.workflow)

    def test_probe_is_owner_scoped_and_provider_non_mutating(self):
        self.assertIn("SOVARA_GCP_AUTHORITY_PROBE_V2", self.workflow)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.workflow)
        self.assertIn("mutation_attempted':False", self.workflow)
        self.assertIn("No IAM, API, deployment, traffic", self.workflow)
        self.assertNotIn(PATH, self.policy.get("provider_mutation_workflow_allowlist", []))

    def test_enabled_service_diagnostic_uses_supported_read_only_cli(self):
        self.assertIn("'services','list','--enabled'", self.workflow)
        self.assertIn("--filter=config.name=", self.workflow)
        self.assertNotIn("gcloud('services','describe'", self.workflow)


    def test_receipt_never_persists_raw_provider_http_bodies(self):
        self.assertIn("def proof_only_http", self.workflow)
        self.assertIn("'raw_body_recorded':False", self.workflow)
        self.assertIn("'raw_authenticated_response_bodies_recorded':False", self.workflow)
        for unsafe_assignment in (
            "'operator_authenticated_status':operator_status",
            "'operator_architron_read':operator_architron",
            "'archon_authenticated_reads':archon_reads",
        ):
            with self.subTest(unsafe_assignment=unsafe_assignment):
                self.assertNotIn(unsafe_assignment, self.workflow)
        for proof_only_assignment in (
            "'operator_authenticated_status':proof_only_http(operator_status)",
            "'operator_architron_read':proof_only_http(operator_architron)",
            "'archon_authenticated_reads':{command:proof_only_http(result)",
        ):
            with self.subTest(proof_only_assignment=proof_only_assignment):
                self.assertIn(proof_only_assignment, self.workflow)


if __name__ == "__main__":
    unittest.main()
