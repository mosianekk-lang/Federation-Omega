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
        self.assertEqual(set(inputs), {"scope", "drift_threshold", "max_copilot_assignments"})
        self.assertEqual(inputs["max_copilot_assignments"]["default"], "3")
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
        self.assertEqual(self.doc["jobs"]["create-resolution-issue"]["permissions"], {"issues": "write"})
        self.assertNotRegex(self.text, r"(?i)contents:\s*write|pull-requests:\s*write|id-token:\s*write|write-all")
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

    def test_copilot_assignment_is_bounded_and_fail_soft(self):
        issue_job = self.doc["jobs"]["create-resolution-issue"]
        script = next(step["run"] for step in issue_job["steps"]
                      if step.get("name") == "Create or update resolution issues")
        self.assertIn('"--add-assignee", "@copilot"', script)
        self.assertIn('"--add-label", "ai-team/in-progress"', script)
        self.assertIn("assignment_attempts >= max_assignments", script)
        self.assertIn("best_effort_gh", script)
        self.assertIn('"ai-team/needs-human"', script)
        self.assertIn('"issue", "comment"', script)
        self.assertIn('if duplicate:', script)
        self.assertLess(script.index("if duplicate:"), script.index('"issue", "create"'))
        self.assertIn('if severity == "low" and scope == "all":', script)
        self.assertIn('elif kinds == ["missing_version_key"]:', self.text)
        self.assertIn("replace(\"`\", \"'\").replace(\"@\", \"＠\")", script)
        self.assertIn(".github/instructions/ai-team-mandate.md", script)
        self.assertNotRegex(script.lower(), r"gh api\s+(?:--method|-x)")

    def test_instructions_document_phases(self):
        doc = INSTRUCTIONS.read_text(encoding="utf-8")
        for marker in ("Superior Logic", "EvidenceOps", "Alpha-Omega Commercial", "ECASP",
                       "CI test scan", "Root cause investigation", "semantic drift", "Resolution report",
                       "max_copilot_assignments", "fine-grained PAT", "workflow_dispatch", "draft/review-only"):
            self.assertIn(marker, doc)


if __name__ == "__main__":
    unittest.main()
