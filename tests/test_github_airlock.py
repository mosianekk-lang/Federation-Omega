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

    def test_bubbles_command_bus_exact_read_only_contract_passes(self):
        text = """name: Bubbles Command Bus
on:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
  pull-requests: read
concurrency:
  group: bubbles-command-bus-${{ github.ref }}
  cancel-in-progress: false
jobs:
  command:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/bubbles-command-bus.yml", text, POLICY
        )
        self.assertEqual([], findings)

    def test_bubbles_provider_worker_exact_oidc_contract_passes(self):
        text = """name: Bubbles Provider Worker
on:
  workflow_run:
permissions:
  contents: read
  actions: read
concurrency:
  group: bubbles-provider-worker
jobs:
  cloud:
    permissions:
      contents: read
      actions: read
      id-token: write
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
      - uses: google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093
      - uses: google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/bubbles-provider-worker.yml", text, POLICY
        )
        self.assertEqual([], findings)

    def test_only_provider_worker_is_allowed_bubbles_oidc(self):
        self.assertEqual(
            [".github/workflows/bubbles-provider-worker.yml"],
            POLICY["oidc_workflow_allowlist"],
        )

    def test_bubbles_provider_worker_cannot_add_pull_request_or_schedule_trigger(self):
        text = """name: Bubbles Provider Worker
on:
  workflow_run:
  pull_request:
  schedule:
    - cron: '0 * * * *'
permissions:
  contents: read
  id-token: write
concurrency:
  group: bubbles-provider-worker
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/bubbles-provider-worker.yml", text, POLICY
        )
        self.assertIn("UNAUTHORISED_TRIGGER", self.rules(findings))

    def test_bubbles_provider_worker_cannot_gain_source_or_actions_write(self):
        text = """name: Bubbles Provider Worker
on:
  workflow_run:
permissions:
  contents: write
  actions: write
  id-token: write
concurrency:
  group: bubbles-provider-worker
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/bubbles-provider-worker.yml", text, POLICY
        )
        rules = self.rules(findings)
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", rules)
        self.assertIn("UNAUTHORISED_ACTIONS_WRITE", rules)

    def test_bubbles_command_bus_cannot_add_schedule(self):
        text = """name: Bubbles Command Bus
on:
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: '0 * * * *'
permissions:
  contents: read
concurrency:
  group: bubbles-command-bus
jobs:
  command:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/bubbles-command-bus.yml", text, POLICY
        )
        self.assertIn("UNAUTHORISED_TRIGGER", self.rules(findings))

    def test_bubbles_command_bus_cannot_gain_oidc_or_source_write(self):
        text = """name: Bubbles Command Bus
on:
  workflow_dispatch:
permissions:
  contents: write
  id-token: write
concurrency:
  group: bubbles-command-bus
jobs:
  command:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/bubbles-command-bus.yml", text, POLICY
        )
        rules = self.rules(findings)
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", rules)
        self.assertIn("UNAUTHORISED_OIDC", rules)

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

    def test_statuses_write_is_rejected_for_normal_workflow(self):
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml",
            "name: Guard\non:\n  pull_request:\npermissions:\n  contents: read\n  statuses: write\nconcurrency:\n  group: x\n",
            POLICY,
        )
        self.assertIn("UNAUTHORISED_STATUSES_WRITE", self.rules(findings))

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
  statuses: write
concurrency:
  group: phoenix-freeze
  cancel-in-progress: false
jobs:
  freeze:
    steps:
      - run: gh api -X PUT /repos/x/y/actions/workflows/1/disable
      - run: gh api -X POST /repos/x/y/statuses/abc -f context=phoenix-freeze/verified
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
  statuses: write
concurrency:
  group: phoenix-freeze
jobs:
  freeze:
    steps:
      - run: gh api -X PUT /repos/x/y/actions/workflows/1/disable
      - run: gh api -X POST /repos/x/y/statuses/abc -f context=phoenix-freeze/verified
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/phoenix-emergency-freeze.yml", text, POLICY
        )
        rules = self.rules(findings)
        self.assertIn("REPOSITORY_WRITE_AUTHORITY", rules)
        self.assertIn("QUARANTINE_CONTROLLER_SOURCE_AUTHORITY", rules)

    def test_quarantine_controller_requires_proof_context(self):
        text = """name: Phoenix Emergency Execution Freeze
on:
  push:
  workflow_dispatch:
permissions:
  actions: write
  contents: read
  statuses: write
concurrency:
  group: phoenix-freeze
jobs:
  freeze:
    steps:
      - run: gh api -X PUT /repos/x/y/actions/workflows/1/disable
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/phoenix-emergency-freeze.yml", text, POLICY
        )
        self.assertIn("PROOF_STATUS_ENDPOINT_DRIFT", self.rules(findings))


if __name__ == "__main__":
    unittest.main()
