import json
from pathlib import Path
import unittest

from tools.github_airlock import analyse_workflow


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/fuse-windows-h1-provider-relay-v2.yml"


class MachineDispatchProviderGatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(
            (ROOT / "governance/github_airlock_policy.json").read_text(encoding="utf-8")
        )
        cls.workflow = (ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")

    def rules(self, text):
        return {row.rule for row in analyse_workflow(WORKFLOW_PATH, text, self.policy)}

    def test_exact_machine_gateway_is_explicitly_admitted(self):
        self.assertIn(
            WORKFLOW_PATH,
            self.policy["provider_mutation_machine_dispatch_workflow_allowlist"],
        )
        self.assertEqual(self.policy["allowed_events"][WORKFLOW_PATH], ["workflow_dispatch"])
        self.assertEqual(self.rules(self.workflow), set())

    def test_unlisted_workflow_remains_fail_closed(self):
        self.assertIn(
            "WORKFLOW_NOT_ALLOWLISTED",
            {row.rule for row in analyse_workflow(".github/workflows/unlisted.yml", self.workflow, self.policy)},
        )

    def test_missing_passport_binding_is_rejected(self):
        altered = self.workflow.replace("FUSE-SURFACE-CAPABILITY-PASSPORT-V1", "REMOVED", 1)
        self.assertIn("PROVIDER_MUTATION_MACHINE_GUARD_MISSING", self.rules(altered))

    def test_owner_issue_trigger_cannot_alias_machine_gateway(self):
        altered = self.workflow.replace("workflow_dispatch:", "issues:\n    types: [opened]", 1)
        self.assertIn("PROVIDER_MUTATION_MACHINE_TRIGGER_DRIFT", self.rules(altered))

    def test_unsafe_ingress_or_traffic_mutation_is_rejected(self):
        altered = self.workflow + "\n# gcloud run services update-traffic\n"
        self.assertIn("PROVIDER_MUTATION_FORBIDDEN_BEHAVIOR", self.rules(altered))


if __name__ == "__main__":
    unittest.main()
