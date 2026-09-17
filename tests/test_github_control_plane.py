from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "github_control_plane.py"
SPEC = importlib.util.spec_from_file_location("github_control_plane", MODULE_PATH)
assert SPEC and SPEC.loader
CONTROL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTROL
SPEC.loader.exec_module(CONTROL)
POLICY = CONTROL.load_policy(ROOT / "governance" / "github_control_plane_policy.json")


class GitHubControlPlaneTests(unittest.TestCase):
    def analyse(self, text: str, filename: str = "test.yml"):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / filename
            path.write_text(text, encoding="utf-8")
            return CONTROL.analyse_workflow_text(
                f".github/workflows/{filename}",
                text,
                POLICY,
            )

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

    def test_forbidden_pattern_exception_is_honoured(self):
        text = """name: Emergency Freeze
on: workflow_dispatch
permissions:
  contents: read
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - run: gh api --method PUT /repos/example/example
"""
        findings, _ = CONTROL.analyse_workflow_text(
            ".github/workflows/phoenix-emergency-freeze.yml",
            text,
            POLICY,
        )
        self.assertNotIn("FORBIDDEN_REPOSITORY_MUTATION_COMMAND", self.rules(findings))

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

    def test_schedule_is_owner_disabled_even_with_concurrency(self):
        findings, _ = self.analyse(
            """name: Scheduled Check
on:
  schedule:
    - cron: '0 3 * * *'
permissions:
  contents: read
concurrency:
  group: scheduled-check
jobs: {}
"""
        )
        self.assertIn("SCHEDULED_WORKFLOW_OWNER_DISABLED", self.rules(findings))

    def test_schedule_requires_concurrency_too(self):
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
        rules = self.rules(findings)
        self.assertIn("SCHEDULED_WORKFLOW_OWNER_DISABLED", rules)
        self.assertIn("MISSING_CONCURRENCY_CONTROL", rules)

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

    def test_pull_request_target_is_zero_trust(self):
        findings, _ = self.analyse(
            """name: PR Target
on:
  pull_request_target:
permissions:
  contents: read
concurrency:
  group: pr-target
jobs: {}
"""
        )
        self.assertIn("PULL_REQUEST_TARGET_ZERO_TRUST", self.rules(findings))

    def test_pull_request_target_cannot_mint_oidc(self):
        findings, _ = self.analyse(
            """name: Cloud Probe
on:
  pull_request_target:
permissions:
  contents: read
  id-token: write
concurrency:
  group: cloud-probe
jobs: {}
"""
        )
        rules = self.rules(findings)
        self.assertIn("PULL_REQUEST_TARGET_ZERO_TRUST", rules)
        self.assertIn("PULL_REQUEST_TARGET_OIDC", rules)
        self.assertIn("OIDC_WORKFLOW_NOT_REGISTERED", rules)

    def test_unregistered_oidc_is_rejected(self):
        findings, _ = self.analyse(
            """name: Cloud Probe
on: workflow_dispatch
permissions:
  contents: read
  id-token: write
concurrency:
  group: cloud-probe
jobs: {}
"""
        )
        self.assertIn("OIDC_WORKFLOW_NOT_REGISTERED", self.rules(findings))

    def test_oidc_requires_concurrency(self):
        findings, _ = self.analyse(
            """name: Cloud Probe
on: workflow_dispatch
permissions:
  contents: read
  id-token: write
jobs: {}
"""
        )
        self.assertIn("OIDC_WITHOUT_CONCURRENCY", self.rules(findings))

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
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
"""
        )
        self.assertIn("CHECKOUT_CREDENTIALS_PERSISTED", self.rules(findings))

    def test_mutable_action_reference_is_hard_failure(self):
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
        self.assertIn("ACTION_NOT_IMMUTABLY_PINNED", self.rules(findings))
        self.assertEqual([], warnings)

    def test_explicit_permissions_are_required(self):
        findings, _ = self.analyse(
            """name: CI
on: workflow_dispatch
jobs: {}
"""
        )
        self.assertIn("MISSING_EXPLICIT_PERMISSIONS", self.rules(findings))

    def test_write_all_is_forbidden(self):
        findings, _ = self.analyse(
            """name: CI
on: workflow_dispatch
permissions: write-all
jobs: {}
"""
        )
        self.assertIn("WRITE_ALL_PERMISSIONS_FORBIDDEN", self.rules(findings))

    def test_read_only_manual_github_agent_passes(self):
        findings, warnings = CONTROL.analyse_agent_profile_text(
            ".github/agents/federation-github-guardian.agent.md",
            """---
name: federation-github-guardian
description: Read-only GitHub estate guardian
target: github-copilot
tools: ["read", "search", "github/*"]
disable-model-invocation: true
user-invocable: true
---
Read only.
""",
            POLICY,
        )
        self.assertEqual([], findings)
        self.assertEqual([], warnings)

    def test_agent_without_tools_is_rejected(self):
        findings, _ = CONTROL.analyse_agent_profile_text(
            ".github/agents/unsafe.agent.md",
            """---
name: unsafe
description: unsafe implicit tools
target: github-copilot
disable-model-invocation: true
---
No tool restriction.
""",
            POLICY,
        )
        self.assertIn("AGENT_TOOLS_IMPLICIT_ALL", self.rules(findings))

    def test_agent_wildcard_or_execution_tools_are_rejected(self):
        wildcard, _ = CONTROL.analyse_agent_profile_text(
            ".github/agents/unsafe.agent.md",
            """---
name: unsafe
description: unsafe wildcard
target: github-copilot
tools: ["*"]
disable-model-invocation: true
---
Unsafe.
""",
            POLICY,
        )
        self.assertIn("AGENT_WILDCARD_TOOLS", self.rules(wildcard))

        privileged, _ = CONTROL.analyse_agent_profile_text(
            ".github/agents/unsafe.agent.md",
            """---
name: unsafe
description: unsafe executor
target: github-copilot
tools: ["read", "edit", "execute"]
disable-model-invocation: true
---
Unsafe.
""",
            POLICY,
        )
        self.assertIn("AGENT_PRIVILEGED_TOOLS_NOT_REGISTERED", self.rules(privileged))

    def test_agent_auto_invocation_is_rejected(self):
        findings, _ = CONTROL.analyse_agent_profile_text(
            ".github/agents/auto.agent.md",
            """---
name: auto
description: auto
target: github-copilot
tools: ["read", "search"]
---
Auto.
""",
            POLICY,
        )
        self.assertIn("AGENT_NOT_MANUAL_INVOCATION", self.rules(findings))

    def test_unregistered_hook_is_rejected(self):
        findings, _ = CONTROL.analyse_hook_text(
            ".github/hooks/tool-guard.json",
            '{"version":1,"hooks":{}}',
            POLICY,
        )
        self.assertIn("COPILOT_HOOK_NOT_REGISTERED", self.rules(findings))

    def test_frontier_scorecard_improves_when_debt_is_removed(self):
        unsafe = {
            ".github/workflows/unsafe.yml": """name: Unsafe
on:
  schedule:
    - cron: '0 1 * * *'
permissions:
  contents: read
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        }
        safe = {
            ".github/workflows/safe.yml": """name: Safe
on:
  pull_request:
permissions:
  contents: read
concurrency:
  group: safe
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
"""
        }
        unsafe_score = CONTROL.estate_metrics_from_texts(unsafe, {}, {}, POLICY)["frontier_control_score"]
        safe_score = CONTROL.estate_metrics_from_texts(safe, {}, {}, POLICY)["frontier_control_score"]
        self.assertGreater(safe_score, unsafe_score)
        self.assertEqual(100, safe_score)

    def test_all_repository_agent_profiles_obey_least_privilege(self):
        for path in CONTROL.agent_profile_files():
            findings, _ = CONTROL.analyse(path, POLICY)
            self.assertEqual([], findings, f"{path}: {findings}")

    def test_no_unregistered_copilot_hooks_exist(self):
        for path in CONTROL.hook_files():
            findings, _ = CONTROL.analyse(path, POLICY)
            self.assertEqual([], findings, f"{path}: {findings}")


if __name__ == "__main__":
    unittest.main()
