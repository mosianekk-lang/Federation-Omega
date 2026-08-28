import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "github_airlock_policy.json"
PHOENIX_PATH = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
PROVIDER_PATH = ".github/workflows/sovara-litellm-v2-3-provider-admission.yml"
PROVIDER_FILE = "sovara-litellm-v2-3-provider-admission.yml"
CIOS_PATH = ".github/workflows/cios-production-lane.yml"
MATURATION_PATH = ".github/workflows/superior-logic-maturation-shadow.yml"
MATURATION_FILE = "superior-logic-maturation-shadow.yml"


class PhoenixRequiredWorkflowAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.phoenix = PHOENIX_PATH.read_text(encoding="utf-8")

    def test_policy_has_one_required_workflow_projection(self) -> None:
        self.assertEqual(
            set(self.policy["active_workflow_allowlist"]),
            set(self.policy["execution_quarantine"]["keep_active"]),
        )

    def test_provider_gateways_and_maturation_runtime_are_airlock_admitted(self) -> None:
        active = set(self.policy["active_workflow_allowlist"])
        keep_active = set(self.policy["execution_quarantine"]["keep_active"])
        for path in (PROVIDER_PATH, CIOS_PATH, MATURATION_PATH):
            self.assertIn(path, active)
            self.assertIn(path, keep_active)
        self.assertIn(PROVIDER_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertIn(CIOS_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertNotIn(MATURATION_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertEqual(["main"], self.policy["required_push_branches"][PROVIDER_PATH])
        self.assertEqual(["main"], self.policy["required_push_branches"][CIOS_PATH])
        self.assertEqual(["main"], self.policy["required_push_branches"][MATURATION_PATH])
        self.assertEqual(
            {"push", "schedule", "workflow_dispatch"},
            set(self.policy["allowed_events"][MATURATION_PATH]),
        )

    def test_phoenix_uses_policy_instead_of_second_required_list(self) -> None:
        self.assertIn("policy_path='governance/github_airlock_policy.json'", self.phoenix)
        self.assertIn("jq -r '.active_workflow_allowlist[]'", self.phoenix)
        self.assertIn("grep -Fxq \"${workflow_path}\" /tmp/phoenix-required-workflows.txt", self.phoenix)
        self.assertIn("mapfile -t required_paths", self.phoenix)
        self.assertNotIn("required_specs=(", self.phoenix)

    def test_phoenix_reenable_canary_dispatch_preserves_special_routes(self) -> None:
        self.assertIn(
            f'"{PROVIDER_FILE}|{PROVIDER_PATH}|LiteLLM provider admission"',
            self.phoenix,
        )
        self.assertIn(
            f'"{MATURATION_FILE}|{MATURATION_PATH}|Superior Logic maturation shadow"',
            self.phoenix,
        )
        self.assertIn(
            '"/repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow_file}/dispatches"',
            self.phoenix,
        )

    def test_phoenix_retains_actions_write_only_for_workflow_state_repair(self) -> None:
        self.assertIn("permissions:\n  actions: write", self.phoenix)
        self.assertIn("persist-credentials: false", self.phoenix)
        self.assertIn("/enable", self.phoenix)
        self.assertIn("/disable", self.phoenix)


if __name__ == "__main__":
    unittest.main()
