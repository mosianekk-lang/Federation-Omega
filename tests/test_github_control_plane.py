from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "github_control_plane.py"
SPEC = importlib.util.spec_from_file_location("github_control_plane", MODULE_PATH)
assert SPEC and SPEC.loader
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)
POLICY = CONTROL.load_policy(ROOT / "governance" / "github_control_plane_policy.json")


class GitHubControlPlaneTests(unittest.TestCase):
    def analyse(self, text: str, filename: str = "test.yml"):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / filename
            path.write_text(text, encoding="utf-8")
            return CONTROL.analyse(path, POLICY)

    def rules(self, findings):
        return {finding.rule for finding in findings}

    def test_safe_read_only_workflow_passes(self):
        findings, warnings = self.analyse(
            """name: Safe CI
on:
  pull_request:
permissions:
  contents: read
concurrency:
  group: safe-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
      - run: echo safe
"""
        )
        self.assertEqual([], findings)
        self.assertEqual([], warnings)

    def test_contents_write_is_rejected(self):
        findings, _ = self.analyse(
            """name: Writer
on: workflow_dispatch
permissions:
  contents: write
jobs: {}
"""
        )
        self.assertIn("UNAUTHORISED_CONTENTS_WRITE", self.rules(findings))

    def test_direct_git_push_is_rejected(self):
        findings, _ = self.analyse(
            """name: Unsafe
on: workflow_dispatch
permissions:
  contents: read
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - run: git push origin HEAD:main
"""
        )
        self.assertIn("FORBIDDEN_REPOSITORY_MUTATION_COMMAND", self.rules(findings))

    def test_read_only_name_cannot_write(self):
        findings, _ = self.analyse(
            """name: Read-only Observer
on: workflow_dispatch
permissions:
  contents: write
jobs: {}
""",
            "read-only-observer.yml",
        )
        rules = self.rules(findings)
        self.assertIn("UNAUTHORISED_CONTENTS_WRITE", rules)
        self.assertIn("READ_ONLY_CLASSIFICATION_CONTRADICTION", rules)

    def test_schedule_requires_concurrency(self):
        findings, _ = self.analyse(
            """name: Scheduled Check
on:
  schedule:
    - cron: '0 3 * * *'
permissions:
  contents: read
jobs: {}
"""
        )
        self.assertIn("MISSING_CONCURRENCY_CONTROL", self.rules(findings))

    def test_workflow_run_cannot_write(self):
        findings, _ = self.analyse(
            """name: Observer
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
permissions:
  contents: write
concurrency:
  group: observer
jobs: {}
"""
        )
        self.assertIn("WORKFLOW_RUN_PRIVILEGE_ESCALATION", self.rules(findings))

    def test_pull_request_target_cannot_mint_oidc(self):
        findings, _ = self.analyse(
            """name: Cloud Probe
on:
  pull_request_target:
permissions:
  contents: read
  id-token: write
jobs: {}
"""
        )
        self.assertIn("PULL_REQUEST_TARGET_OIDC", self.rules(findings))

    def test_checkout_must_not_persist_credentials(self):
        findings, _ = self.analyse(
            """name: CI
on: workflow_dispatch
permissions:
  contents: read
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        )
        self.assertIn("CHECKOUT_CREDENTIALS_PERSISTED", self.rules(findings))

    def test_mutable_action_reference_is_reported(self):
        findings, warnings = self.analyse(
            """name: CI
on: workflow_dispatch
permissions:
  contents: read
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
"""
        )
        self.assertEqual([], findings)
        self.assertEqual({"ACTION_NOT_IMMUTABLY_PINNED"}, {warning.rule for warning in warnings})


if __name__ == "__main__":
    unittest.main()
