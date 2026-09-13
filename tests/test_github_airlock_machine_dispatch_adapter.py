import json
from pathlib import Path
import unittest

from tools.github_airlock import analyse_workflow


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/fuse-windows-h1-machine-dispatch-adapter-v1.yml"
TARGET_WORKFLOW = "fuse-windows-h1-provider-relay-v2.yml"


class WindowsH1MachineDispatchAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(
            (ROOT / "governance/github_airlock_policy.json").read_text(encoding="utf-8")
        )
        cls.workflow = (ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")

    def rules(self, text=None):
        return {
            row.rule
            for row in analyse_workflow(
                WORKFLOW_PATH,
                self.workflow if text is None else text,
                self.policy,
            )
        }

    def test_adapter_is_exactly_allowlisted_as_issue_actions_writer(self):
        self.assertIn(WORKFLOW_PATH, self.policy["active_workflow_allowlist"])
        self.assertEqual(self.policy["allowed_events"][WORKFLOW_PATH], ["issues"])
        self.assertIn(WORKFLOW_PATH, self.policy["actions_write_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, self.policy["oidc_workflow_allowlist"])
        self.assertNotIn(WORKFLOW_PATH, self.policy["provider_mutation_workflow_allowlist"])
        self.assertNotIn(
            WORKFLOW_PATH,
            self.policy["provider_mutation_machine_dispatch_workflow_allowlist"],
        )
        self.assertIn(WORKFLOW_PATH, self.policy["execution_quarantine"]["keep_active"])
        self.assertEqual(self.rules(), set())

    def test_adapter_is_owner_gated_and_target_is_hard_coded(self):
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.workflow)
        self.assertIn("[FO-DISPATCH] FUSE_WINDOWS_H1_MACHINE_DISPATCH_V1", self.workflow)
        self.assertIn(f"TARGET_WORKFLOW: {TARGET_WORKFLOW}", self.workflow)
        self.assertIn("/actions/workflows/${TARGET_WORKFLOW}/dispatches", self.workflow)
        self.assertIn("'ref': 'main'", self.workflow)
        self.assertNotIn("workflow_dispatch:", self.workflow)

    def test_adapter_has_no_provider_identity_or_provider_mutation_power(self):
        self.assertIn("actions: write", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertIn("issues: read", self.workflow)
        self.assertNotIn("id-token: write", self.workflow)
        self.assertNotIn("gcloud ", self.workflow)
        self.assertNotIn("google-github-actions/auth", self.workflow)
        self.assertNotIn("--allow-unauthenticated", self.workflow)
        self.assertNotIn("run deploy", self.workflow)
        self.assertNotIn("contents: write", self.workflow)

    def test_adapter_preserves_exact_passport_contract(self):
        required = (
            "FUSE-SURFACE-CAPABILITY-PASSPORT-V1",
            "FUSE_WINDOWS_H1_PROVIDER_RELAY_V2",
            "A2_REVERSIBLE_ISOLATED_CANARY",
            "provider_effect_authorized",
            "rollback_required",
            "public_ingress",
            "iam_mutation",
            "customer_traffic",
            "gcp_heavy_compute",
            "max_cpu",
            "max_memory_mib",
            "max_instances",
            "PASSPORT_FIELDS_NOT_EXACT",
            "PASSPORT_FIELD_MISMATCH",
            "PASSPORT_TIME_WINDOW_INVALID",
            "PROVIDER_PASSPORT_JSON_B64",
            "PROVIDER_PASSPORT_SHA256",
        )
        for marker in required:
            self.assertIn(marker, self.workflow)

    def test_adapter_cannot_alias_provider_gateway(self):
        self.assertNotIn("permissions:\n  contents: read\n  id-token: write", self.workflow)
        self.assertNotIn("fuse-windows-h1-provider-relay-v2.yml\n  EXPECTED_TITLE", self.workflow)
        self.assertIn("provider_effect_performed_by_adapter': False", self.workflow)
        self.assertIn("provider_credentials_accessed_by_adapter': False", self.workflow)
        self.assertIn("owner_pc_effect_performed_by_adapter': False", self.workflow)


if __name__ == "__main__":
    unittest.main()
