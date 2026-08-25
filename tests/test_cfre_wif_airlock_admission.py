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
WORKFLOW = ".github/workflows/cfre-operator-deploy.yml"


class CfreWifAirlockAdmissionTests(unittest.TestCase):
    def test_exact_cfre_gateway_is_admitted(self):
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertEqual([], AIRLOCK.analyse_workflow(WORKFLOW, text, POLICY))

    def test_only_dispatch_is_authorized_for_cfre_gateway(self):
        self.assertEqual(["workflow_dispatch"], POLICY["allowed_events"][WORKFLOW])

    def test_cfre_gateway_is_exactly_oidc_allowlisted(self):
        self.assertIn(WORKFLOW, POLICY["active_workflow_allowlist"])
        self.assertIn(WORKFLOW, POLICY["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW, POLICY["execution_quarantine"]["keep_active"])

    def test_unlisted_oidc_workflow_remains_denied(self):
        text = """name: Unlisted OIDC\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n  id-token: write\nconcurrency:\n  group: denied\n"""
        rules = {item.rule for item in AIRLOCK.analyse_workflow(".github/workflows/unlisted-oidc.yml", text, POLICY)}
        self.assertIn("WORKFLOW_NOT_ALLOWLISTED", rules)
        self.assertIn("UNAUTHORISED_OIDC", rules)
        self.assertIn("UNAUTHORISED_TRIGGER", rules)

    def test_gateway_has_no_repository_write_authority(self):
        text = (ROOT / WORKFLOW).read_text(encoding="utf-8")
        self.assertFalse(AIRLOCK.has_contents_write(text))
        self.assertFalse(AIRLOCK.has_actions_write(text))
        self.assertFalse(AIRLOCK.has_statuses_write(text))


if __name__ == "__main__":
    unittest.main()

