from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("github_airlock", ROOT / "tools" / "github_airlock.py")
assert SPEC and SPEC.loader
AIRLOCK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AIRLOCK
SPEC.loader.exec_module(AIRLOCK)
POLICY = AIRLOCK.load_policy(ROOT / "governance" / "github_airlock_policy.json")
WORKFLOW = ".github/workflows/federation-automation-gateway-activate.yml"


class FederationAutomationGatewayAirlockTests(unittest.TestCase):
    def test_actual_activation_workflow_passes_airlock(self):
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertEqual([], AIRLOCK.analyse_workflow(WORKFLOW, text, POLICY))

    def test_activation_is_main_push_only_oidc_and_source_read_only(self):
        policy = POLICY
        self.assertEqual(policy["allowed_events"][WORKFLOW], ["push"])
        self.assertEqual(policy["required_push_branches"][WORKFLOW], ["main"])
        self.assertIn(WORKFLOW, policy["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW, policy["execution_quarantine"]["keep_active"])
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("git push", text.lower())
        self.assertNotIn("workflow_dispatch", text)

    def test_activation_is_bound_to_owner_created_wif_and_runtime_identity(self):
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertIn("fed-bootstrap-pool/providers/github-fed-omega", text)
        self.assertIn("federation-bootstrap-admin@sov-hybrid-suite.iam.gserviceaccount.com", text)
        self.assertIn("federation-automation-runtime@sov-hybrid-suite.iam.gserviceaccount.com", text)
        self.assertIn("BOOTSTRAP_EXPIRY_NOT_FOUND", text)
        self.assertIn("BOOTSTRAP_AUTHORITY_EXPIRED", text)
        self.assertIn("--no-allow-unauthenticated", text)
        self.assertIn("--max-instances 1", text)
        self.assertIn("--concurrency 1", text)


if __name__ == "__main__":
    unittest.main()
