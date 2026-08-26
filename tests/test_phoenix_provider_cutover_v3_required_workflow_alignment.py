import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "governance" / "github_airlock_policy.json"
PHOENIX_PATH = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
PROVIDER_PATH = ".github/workflows/sovara-litellm-v2-3-provider-admission.yml"
PROVIDER_FILE = "sovara-litellm-v2-3-provider-admission.yml"


class PhoenixRequiredWorkflowAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.phoenix = PHOENIX_PATH.read_text(encoding="utf-8")

    def test_provider_gateway_is_airlock_admitted_and_oidc_scoped(self) -> None:
        self.assertIn(PROVIDER_PATH, self.policy["active_workflow_allowlist"])
        self.assertIn(PROVIDER_PATH, self.policy["execution_quarantine"]["keep_active"])
        self.assertIn(PROVIDER_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertEqual(["main"], self.policy["required_push_branches"][PROVIDER_PATH])

    def test_phoenix_keeps_provider_gateway_active(self) -> None:
        self.assertIn(f"{PROVIDER_PATH})", self.phoenix)
        self.assertIn(
            f'"{PROVIDER_FILE}|{PROVIDER_PATH}"',
            self.phoenix,
        )

    def test_phoenix_dispatches_provider_gateway_after_reenable(self) -> None:
        self.assertIn(
            f'"{PROVIDER_FILE}|{PROVIDER_PATH}|LiteLLM provider admission"',
            self.phoenix,
        )
        self.assertIn(
            '"/repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow_file}/dispatches"',
            self.phoenix,
        )

    def test_phoenix_retains_actions_write_for_workflow_state_repair(self) -> None:
        self.assertIn("permissions:\n  actions: write", self.phoenix)
        self.assertIn("persist-credentials: false", self.phoenix)


if __name__ == "__main__":
    unittest.main()
