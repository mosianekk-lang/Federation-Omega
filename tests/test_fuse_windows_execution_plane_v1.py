from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLANE = ROOT / "windows_federation_plane"


class FederationWindowsPlaneSourceTests(unittest.TestCase):
    def test_complete_project_contract_exists(self):
        for name in ("README.md", "FORMATION_SPEC.md", "PROJECT_MEMORY.md", "AI_HANDOFF.md", "THREAT_MODEL.md", "BUILD_CONTRACT.json"):
            self.assertTrue((PLANE / name).is_file(), name)

    def test_workflow_is_windows_and_least_privilege(self):
        source = (ROOT / ".github/workflows/fuse-windows-execution-plane-v1.yml").read_text(encoding="utf-8")
        self.assertIn("runs-on: windows-latest", source)
        self.assertIn("contents: read", source)
        self.assertNotIn("id-token: write", source)
        self.assertIn("persist-credentials: false", source)
        self.assertIn("timeout-minutes: 15", source)
        self.assertIn("github.event.pull_request.head.sha || github.sha", source)
        self.assertIn("verify_receipt_mapping", source)
        self.assertNotIn("actions/checkout@v", source)
        self.assertNotIn("actions/setup-python@v", source)
        self.assertNotIn("actions/upload-artifact@v", source)

    def test_no_arbitrary_command_surface(self):
        source = (PLANE / "src/federation_windows_plane/executor.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "shell=True", "Invoke-Expression"):
            self.assertNotIn(forbidden, source)
        cli = (PLANE / "src/federation_windows_plane/cli.py").read_text(encoding="utf-8")
        self.assertNotIn('"--envelope"', cli)

    def test_governance_is_additive(self):
        data = json.loads((ROOT / "governance/fuse_windows_execution_plane_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(data["parent_controller"], "FUSE-OMEGA-INFINITY")
        self.assertFalse(data["creates_new_sovereign_plane"])
        self.assertEqual(data["provider_effect"], "NONE_UNTIL_SEPARATELY_AUTHORIZED")

    def test_airlock_admits_only_the_bounded_workflow_events(self):
        workflow = ".github/workflows/fuse-windows-execution-plane-v1.yml"
        policy = json.loads((ROOT / "governance/github_airlock_policy.json").read_text(encoding="utf-8"))
        self.assertIn(workflow, policy["active_workflow_allowlist"])
        self.assertIn(workflow, policy["execution_quarantine"]["keep_active"])
        self.assertEqual(policy["allowed_events"][workflow], ["pull_request", "workflow_dispatch"])
        self.assertNotIn(workflow, policy["oidc_workflow_allowlist"])
        self.assertNotIn(workflow, policy["provider_mutation_workflow_allowlist"])


if __name__ == "__main__":
    unittest.main()
