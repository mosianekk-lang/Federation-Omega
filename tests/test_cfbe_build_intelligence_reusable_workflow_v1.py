from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github/workflows/cfbe-build-intelligence-reusable-v1.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
POLICY = ROOT / "governance/github_airlock_policy.json"
WORKFLOW_PATH = ".github/workflows/cfbe-build-intelligence-reusable-v1.yml"


class ReusableWorkflowContractTests(unittest.TestCase):
    def test_reusable_only_and_read_only(self):
        self.assertIn("workflow_call:", TEXT)
        self.assertNotIn("workflow_dispatch:", TEXT)
        self.assertNotIn("schedule:", TEXT)
        self.assertIn("permissions:\n  contents: read", TEXT)
        self.assertNotIn("contents: write", TEXT)
        self.assertNotIn("id-token: write", TEXT)

    def test_every_action_is_immutably_pinned(self):
        uses = re.findall(r"uses:\s*([^\s]+)", TEXT)
        self.assertGreaterEqual(len(uses), 3)
        self.assertTrue(all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in uses), uses)
        self.assertNotRegex(TEXT, r"uses:\s*[^\s]+@v\d")

    def test_known_repository_pins_are_used(self):
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", TEXT)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", TEXT)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", TEXT)
        self.assertIn("persist-credentials: false", TEXT)

    def test_source_epoch_is_exact_and_proof_bearing(self):
        self.assertIn('test "$(git rev-parse HEAD)" = "${EXPECTED_SOURCE_SHA}"', TEXT)
        self.assertIn("source-manifest.json", TEXT)
        self.assertIn("sbom.cdx.json", TEXT)
        self.assertIn("provenance.intoto.json", TEXT)
        self.assertIn("sha256sum proof/*.json", TEXT)

    def test_workflow_runs_all_focused_courts(self):
        self.assertIn("tests.test_cfbe_build_intelligence_adapter_v1", TEXT)
        self.assertIn("tests.test_cfbe_compatibility_propagation_v1", TEXT)
        self.assertIn("tests.test_cfbe_build_intelligence_reusable_workflow_v1", TEXT)

    def test_airlock_admits_only_reusable_read_only_event(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertIn(WORKFLOW_PATH, policy["active_workflow_allowlist"])
        self.assertEqual(policy["allowed_events"][WORKFLOW_PATH], ["workflow_call"])
        self.assertNotIn(WORKFLOW_PATH, policy["oidc_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, policy["provider_mutation_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, policy["attestations_write_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, policy["actions_write_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, policy["statuses_write_workflow_allowlist"])


if __name__ == "__main__":
    unittest.main()
