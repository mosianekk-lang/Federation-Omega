import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    ".github/workflows/nexus-direct-preflight.yml",
    ".github/workflows/nexus-direct-runtime-target.yml",
)
POLICY = ROOT / "governance" / "github_airlock_policy.json"
PINNED = (
    "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
    "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093",
    "google-github-actions/setup-gcloud@e427ad8a34f8676edf47cf7d7925499adf3eb74f",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
)


class NexusEnabledServiceDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_provider_preflights_are_read_only_oidc_artifact_lanes(self) -> None:
        if not all((ROOT / rel).exists() for rel in PATHS):
            self.skipTest("workflow-free export excludes repository workflow controls")
        for rel in PATHS:
            with self.subTest(path=rel):
                workflow = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("contents: read", workflow)
                self.assertIn("id-token: write", workflow)
                self.assertIn("persist-credentials: false", workflow)
                self.assertNotIn("contents: write", workflow)
                self.assertNotIn("git push", workflow)
                self.assertNotIn("git commit", workflow)
                self.assertNotIn("git tag", workflow)
                for action in PINNED:
                    self.assertIn(action, workflow)
                self.assertIn("'services','list','--enabled'", workflow)
                self.assertIn("--filter=config.name=", workflow)
                self.assertNotIn("'services','describe',api", workflow)
                self.assertIn("'mutation_attempted':False", workflow)
                self.assertIn("'secret_values_recorded':False", workflow)

    def test_airlock_contract_is_exact_manual_read_only_preflight(self) -> None:
        active = set(self.policy["active_workflow_allowlist"])
        oidc = set(self.policy["oidc_workflow_allowlist"])
        keep_active = set(self.policy["execution_quarantine"]["keep_active"])
        mutation = set(self.policy.get("provider_mutation_workflow_allowlist", []))
        for rel in PATHS:
            with self.subTest(path=rel):
                self.assertIn(rel, active)
                self.assertIn(rel, oidc)
                self.assertIn(rel, keep_active)
                self.assertEqual(["workflow_dispatch"], self.policy["allowed_events"][rel])
                self.assertNotIn(rel, mutation)


if __name__ == "__main__":
    unittest.main()
