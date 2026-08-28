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

    def test_activation_is_main_scoped_oidc_and_source_read_only(self):
        self.assertEqual(POLICY["allowed_events"][WORKFLOW], ["push", "workflow_dispatch"])
        self.assertEqual(POLICY["required_push_branches"][WORKFLOW], ["main"])
        self.assertIn(WORKFLOW, POLICY["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW, POLICY["execution_quarantine"]["keep_active"])
        self.assertEqual(
            sorted(POLICY["active_workflow_allowlist"]),
            sorted(POLICY["execution_quarantine"]["keep_active"]),
        )
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("git push", text.lower())

    def test_activation_uses_dedicated_wif_existing_deployer_and_runtime(self):
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertIn("github-federation-omega/providers/luna-automation-gateway", text)
        self.assertIn("superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com", text)
        self.assertIn("superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com", text)
        self.assertNotIn("federation-bootstrap-admin", text)
        self.assertNotIn("BOOTSTRAP_EXPIRY_NOT_FOUND", text)
        self.assertNotIn("BOOTSTRAP_AUTHORITY_EXPIRED", text)
        self.assertNotIn("service-accounts create", text)
        self.assertNotIn("gcloud services enable", text)
        self.assertIn("--no-allow-unauthenticated", text)
        self.assertIn("--max-instances 1", text)
        self.assertIn("--concurrency 1", text)

    def test_activation_receipt_preserves_runtime_authority_boundary(self):
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertIn("provider_admin_runtime_lane':'UNBOUND_FAIL_CLOSED'", text)
        self.assertIn("assert health.get('elevated_identity_bound') is False", text)
        self.assertIn("sheet_acl_canary_pending", text)
        self.assertIn("command_receipt_canary_pending", text)


if __name__ == "__main__":
    unittest.main()
