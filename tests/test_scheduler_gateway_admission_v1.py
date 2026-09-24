from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "github_airlock_scheduler_gateway",
    ROOT / "tools" / "github_airlock.py",
)
assert SPEC and SPEC.loader
AIRLOCK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AIRLOCK
SPEC.loader.exec_module(AIRLOCK)

WORKFLOW = ".github/workflows/evidenceops-external-scheduler.yml"


class SchedulerGatewayAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(
            (ROOT / "governance" / "github_airlock_policy.json").read_text(encoding="utf-8")
        )
        self.text = (ROOT / WORKFLOW).read_text(encoding="utf-8")

    def test_gateway_is_explicitly_allowlisted_and_kept_active(self):
        self.assertIn(WORKFLOW, self.policy["active_workflow_allowlist"])
        self.assertIn(WORKFLOW, self.policy["execution_quarantine"]["keep_active"])

    def test_event_contract_is_exact_and_push_is_main_only(self):
        self.assertEqual(
            {"schedule", "workflow_dispatch", "push"},
            set(self.policy["allowed_events"][WORKFLOW]),
        )
        self.assertEqual(["main"], self.policy["required_push_branches"][WORKFLOW])

    def test_airlock_accepts_hardened_gateway(self):
        self.assertEqual([], AIRLOCK.analyse_workflow(WORKFLOW, self.text, self.policy))

    def test_immutable_actions_and_checkout_credentials(self):
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            self.text,
        )
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            self.text,
        )
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            self.text,
        )

    def test_issue_write_is_scoped_to_scheduler_job(self):
        top = self.text.split("jobs:", 1)[0]
        self.assertNotIn("issues: write", top)
        schedule = self.text.split("jobs:", 1)[1]
        self.assertIn("issues: write", schedule)

    def test_no_source_write_or_actions_write_authority(self):
        self.assertNotIn("contents: write", self.text)
        self.assertNotIn("actions: write", self.text)
        self.assertNotIn("id-token: write", self.text)


if __name__ == "__main__":
    unittest.main()
