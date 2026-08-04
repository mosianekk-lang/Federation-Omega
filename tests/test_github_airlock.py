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
        text = """name: Public Repository Leak Guard
on:
  pull_request:
  push:
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: guard-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml", text, POLICY
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
            ".github/workflows/public-repository-leak-guard.yml",
            "name: Guard\non:\n  pull_request:\npermissions:\n  contents: write\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", self.rules(findings))

    def test_actions_write_is_rejected_for_normal_workflow(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml",
            "name: Guard\non:\n  pull_request:\npermissions:\n  contents: read\n  actions: write\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("UNAUTHORISED_ACTIONS_WRITE", self.rules(findings))

    def test_git_push_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml",
            "name: Guard\non:\n  pull_request:\npermissions:\n  contents: read\nconcurrency:\n  group: x\njobs:\n  x:\n    steps:\n      - run: git push origin HEAD:main\n",
            POLICY,
        )
        self.assertIn("FORBIDDEN_REPOSITORY_MUTATION", self.rules(findings))

    def test_mutable_action_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml",
            "name: Guard\non:\n  pull_request:\npermissions:\n  contents: read\nconcurrency:\n  group: x\njobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          persist-credentials: false\n",
            POLICY,
        )
        self.assertIn("MUTABLE_ACTION_REFERENCE", self.rules(findings))

    def test_unapproved_oidc_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml",
            "name: Guard\non:\n  pull_request:\npermissions:\n  contents: read\n  id-token: write\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("UNAUTHORISED_OIDC", self.rules(findings))

    def test_unapproved_trigger_is_rejected(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml",
            "name: Guard\non:\n  schedule:\n    - cron: '0 * * * *'\npermissions:\n  contents: read\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("UNAUTHORISED_TRIGGER", self.rules(findings))

    def test_quarantine_controller_contract_passes(self):
        text = """name: Phoenix Emergency Execution Freeze
on:
  push:
  workflow_dispatch:
permissions:
  actions: write
  contents: read
concurrency:
  group: phoenix-freeze
  cancel-in-progress: false
jobs:
  freeze:
    steps:
      - run: gh api --method PUT /repos/x/y/actions/workflows/1/disable
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/phoenix-emergency-freeze.yml", text, POLICY
        )
        self.assertEqual([], findings)

    def test_quarantine_controller_cannot_mutate_source(self):
        text = """name: Phoenix Emergency Execution Freeze
on:
  push:
  workflow_dispatch:
permissions:
  actions: write
  contents: write
concurrency:
  group: phoenix-freeze
jobs:
  freeze:
    steps:
      - run: gh api --method PUT /repos/x/y/actions/workflows/1/disable
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/phoenix-emergency-freeze.yml", text, POLICY
        )
        rules = self.rules(findings)
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", rules)
        self.assertIn("QUARANTINE_CONTROLLER_SOURCE_AUTHORITY", rules)


if __name__ == "__main__":
    unittest.main()
