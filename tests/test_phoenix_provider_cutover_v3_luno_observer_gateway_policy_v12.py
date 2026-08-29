import json
import re
import unittest
from pathlib import Path


WORKFLOW = ".github/workflows/luno-observer-provider-binding.yml"


class LunoObserverGatewayPolicyV12Tests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(Path("governance/github_airlock_policy.json").read_text(encoding="utf-8"))
        self.workflow = Path(WORKFLOW).read_text(encoding="utf-8")

    def test_gateway_is_exactly_registered_in_airlock_policy(self):
        self.assertEqual(self.policy["policy_id"], "FEDOMEGA-GITHUB-AIRLOCK-V2")
        version = tuple(int(part) for part in self.policy["version"].split("."))
        self.assertEqual(version[0], 2)
        self.assertGreaterEqual(version, (2, 7, 0))
        self.assertIn(WORKFLOW, self.policy["active_workflow_allowlist"])
        self.assertIn(WORKFLOW, self.policy["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW, self.policy["execution_quarantine"]["keep_active"])
        self.assertEqual(
            set(self.policy["allowed_events"][WORKFLOW]),
            {"pull_request", "push", "workflow_dispatch"},
        )
        self.assertEqual(self.policy["required_push_branches"][WORKFLOW], ["main"])
        self.assertEqual(
            self.policy["provider_credential_reference_policy"]["luno_observer_deployment_workflow"],
            WORKFLOW,
        )

    def test_gateway_gets_oidc_but_no_source_actions_or_status_write(self):
        self.assertIn("id-token: write", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("actions: write", self.workflow)
        self.assertNotIn("statuses: write", self.workflow)
        self.assertNotIn(WORKFLOW, self.policy["actions_write_workflow_allowlist"])
        self.assertNotIn(WORKFLOW, self.policy["statuses_write_workflow_allowlist"])

    def test_all_external_actions_are_immutable_sha_pins(self):
        refs = re.findall(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", self.workflow)
        self.assertGreaterEqual(len(refs), 5)
        for value in refs:
            if value.startswith("./"):
                continue
            self.assertIn("@", value, value)
            ref = value.rsplit("@", 1)[1]
            self.assertRegex(ref, r"^[0-9a-fA-F]{40}$", value)

    def test_gateway_has_no_repository_or_financial_mutation_route(self):
        lower = self.workflow.lower()
        for marker in (
            "git push",
            "git commit",
            "gh api --method post",
            "gh api --method put",
            "/api/1/postorder",
            "/api/1/marketorder",
            "/api/1/send",
            "/api/1/withdrawals",
            "scheduler jobs create",
        ):
            self.assertNotIn(marker, lower)
        self.assertIn("--no-traffic", self.workflow)
        self.assertIn("LUNO_BINDING_MODE=PUBLIC_ONLY", self.workflow)
        self.assertIn("CREDENTIAL_PERMISSION_PROOF_REQUIRED", self.workflow)

    def test_gateway_does_not_import_legacy_luno_trading_secret_names(self):
        self.assertNotIn("luno-api-key", self.workflow)
        self.assertNotIn("luno-api-secret", self.workflow)
        self.assertIn("luno-observer-key-id", self.workflow)
        self.assertIn("luno-observer-key-material", self.workflow)
        self.assertIn("luno-observer-permission-proof", self.workflow)


if __name__ == "__main__":
    unittest.main()
