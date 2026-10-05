import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "n-omega-supervisor.yml"
INSTRUCTIONS = ROOT / ".github" / "workflows" / "n-omega-supervisor.md"


class NOmegaSupervisorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.doc = yaml.safe_load(self.text)
        self.triggers = self.doc[True]

    def test_triggers(self):
        self.assertEqual(self.triggers["schedule"], [{"cron": "0 0 * * *"}])
        inputs = self.triggers["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), {"scope", "drift_threshold"})
        self.assertEqual(self.triggers["workflow_run"]["types"], ["completed"])

    def test_jobs(self):
        self.assertEqual(
            list(self.doc["jobs"]),
            ["audit-ci-tests", "investigate-failures", "detect-semantic-drift",
             "create-resolution-issue", "publish-audit-logs"],
        )

    def test_least_privilege(self):
        self.assertEqual(self.doc["permissions"], {"actions": "read", "contents": "read"})
        writers = [n for n, j in self.doc["jobs"].items() if "issues" in j.get("permissions", {})]
        self.assertEqual(writers, ["create-resolution-issue"])
        self.assertNotRegex(self.text, r"(?i)contents:\s*write|id-token:\s*write|write-all")
        self.assertNotRegex(self.text.lower(), r"git (push|commit|tag)|gh api (--method|-x)")

    def test_actions_pinned_and_checkout_credentials(self):
        for ref in re.findall(r"uses:\s*\S+@(\S+)", self.text):
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
        self.assertIn("persist-credentials: false", self.text)

    def test_artifacts_retained_30_days(self):
        self.assertEqual(self.text.count("actions/upload-artifact@"), self.text.count("retention-days: 30"))

    def test_issue_contract(self):
        for marker in ("[N-Omega Audit]", "automation/n-omega", "audit/{domain}", "severity/{severity}", "timedelta(days=7)"):
            self.assertIn(marker, self.text)

    def test_instructions_document_phases(self):
        doc = INSTRUCTIONS.read_text(encoding="utf-8")
        for marker in ("Superior Logic", "EvidenceOps", "Alpha-Omega Commercial", "ECASP",
                       "CI test scan", "Root cause investigation", "semantic drift", "Resolution report"):
            self.assertIn(marker, doc)


if __name__ == "__main__":
    unittest.main()
