from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "github_airlock", ROOT / "tools" / "github_airlock.py"
)
assert SPEC and SPEC.loader
AIRLOCK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AIRLOCK
SPEC.loader.exec_module(AIRLOCK)
POLICY = AIRLOCK.load_policy(ROOT / "governance" / "github_airlock_policy.json")


class GitHubAirlockTests(unittest.TestCase):
    def rules(self, findings):
        return {finding.rule for finding in findings}

    def test_read_only_pinned_workflow_passes(self):
        text = """name: EvidenceOps RESOLVE CI
on:
  pull_request:
  merge_group:
  push:
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: resolve-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/evidenceops-resolve-ci.yml", text, POLICY
        )
        self.assertEqual([], findings)

    def test_unlisted_workflow_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/new-bot.yml",
            "name: New Bot\non:\n  workflow_dispatch:\npermissions:\n  contents: read\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("WORKFLOW_NOT_ALLOWLISTED", self.rules(findings))

    def test_contents_write_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/evidenceops-resolve-ci.yml",
            "name: EvidenceOps RESOLVE CI\non:\n  pull_request:\npermissions:\n  contents: write\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", self.rules(findings))

    def test_git_push_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/evidenceops-resolve-ci.yml",
            "name: EvidenceOps RESOLVE CI\non:\n  pull_request:\npermissions:\n  contents: read\nconcurrency:\n  group: x\njobs:\n  x:\n    steps:\n      - run: git push origin HEAD:main\n",
            POLICY,
        )
        self.assertIn("FORBIDDEN_REPOSITORY_MUTATION", self.rules(findings))

    def test_mutable_action_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/evidenceops-resolve-ci.yml",
            "name: EvidenceOps RESOLVE CI\non:\n  pull_request:\npermissions:\n  contents: read\nconcurrency:\n  group: x\njobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          persist-credentials: false\n",
            POLICY,
        )
        self.assertIn("MUTABLE_ACTION_REFERENCE", self.rules(findings))

    def test_unapproved_oidc_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/evidenceops-resolve-ci.yml",
            "name: EvidenceOps RESOLVE CI\non:\n  pull_request:\npermissions:\n  contents: read\n  id-token: write\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("UNAUTHORISED_OIDC", self.rules(findings))

    def test_unapproved_trigger_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/evidenceops-resolve-ci.yml",
            "name: EvidenceOps RESOLVE CI\non:\n  schedule:\n    - cron: '0 * * * *'\npermissions:\n  contents: read\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("UNAUTHORISED_TRIGGER", self.rules(findings))


if __name__ == "__main__":
    unittest.main()
