from __future__ import annotations

import importlib.util
import json
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
  push:
    branches: [main]
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

    def test_bubbles_command_bus_rejects_unscoped_push(self):
        text = """name: Bubbles Command Bus
on:
  push:
  pull_request:
  workflow_dispatch:
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
        self.assertIn("UNAUTHORISED_PUSH_SCOPE", self.rules(findings))

    def test_bubbles_command_bus_rejects_non_main_push_scope(self):
        text = """name: Bubbles Command Bus
on:
  push:
    branches: [main, develop]
  pull_request:
  workflow_dispatch:
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
        self.assertIn("UNAUTHORISED_PUSH_SCOPE", self.rules(findings))

    def test_bubbles_command_bus_cannot_add_schedule(self):
        text = """name: Bubbles Command Bus
on:
  push:
    branches: [main]
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
  push:
    branches: [main]
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

    def test_expression_bearing_flow_mapping_is_rejected(self):
        text = """name: Guard
on:
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: x
jobs:
  test:
    steps:
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with: {name: proof-${{ github.run_id }}, path: output}
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml", text, POLICY
        )
        self.assertIn(
            "AMBIGUOUS_WORKFLOW_FLOW_EXPRESSION",
            self.rules(findings),
        )

    def test_current_workflows_have_no_expression_bearing_flow_mappings(self):
        workflow_dir = ROOT / ".github" / "workflows"
        for path in sorted(workflow_dir.glob("*.yml")):
            findings = AIRLOCK.workflow_syntax_findings(
                path.relative_to(ROOT).as_posix(),
                path.read_text(encoding="utf-8"),
            )
            self.assertEqual([], findings, path.name)

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

    def test_provider_mutation_is_rejected_outside_exact_lease(self):
        text = """name: Guard
on:
  pull_request:
permissions:
  contents: read
concurrency:
  group: x
jobs:
  x:
    steps:
      - run: gcloud iam workload-identity-pools providers update-oidc github --project p
"""
        findings = AIRLOCK.analyse_workflow(
            ".github/workflows/public-repository-leak-guard.yml", text, POLICY
        )
        self.assertIn("UNAUTHORISED_PROVIDER_MUTATION", self.rules(findings))

    def test_sol62_wif_hardening_lease_is_exact_and_owner_gated(self):
        workflow = ".github/workflows/sol62-wif-hardening-lease.yml"
        title = "SOL62-WIF-HARDEN-20260901"
        self.assertEqual([workflow], POLICY.get("provider_mutation_workflow_allowlist"))
        self.assertEqual({workflow: title}, POLICY.get("provider_mutation_exact_issue_titles"))
        self.assertIn(workflow, POLICY.get("oidc_workflow_allowlist"))
        self.assertIn(workflow, POLICY.get("active_workflow_allowlist"))
        self.assertIn(workflow, POLICY["execution_quarantine"]["keep_active"])
        path = ROOT / workflow
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("github.event.issue.author_association == 'OWNER'", text)
        self.assertIn(title, text)
        self.assertIn("workload-identity-pools providers update-oidc", text)
        self.assertIn("id-token: write", text)
        self.assertIn("persist-credentials: false", text)
        self.assertEqual([], AIRLOCK.analyse_workflow(workflow, text, POLICY))
        self.assertFalse((ROOT / ".github/workflows/fhu047-wif-least-privilege-apply-v1.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/fhu047-admin-authority-graph-census-v2.yml").exists())

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

    def test_fcx_copilot_agent_profiles_preserve_repository_safety_contract(self):
        profiles = {
            "fcx-builder.agent.md": ("purpose-specific branch", "Never push or commit directly to `main`"),
            "fcx-reviewer.agent.md": ("read-only", "AGENTS.md"),
            "fcx-falsifier.agent.md": ("read-only", "AGENTS.md"),
            "fcx-gemini-challenger.agent.md": ("proposal-only", "Never infer that you are Gemini"),
        }
        agent_dir = ROOT / ".github" / "agents"
        for name, phrases in profiles.items():
            path = agent_dir / name
            self.assertTrue(path.is_file(), name)
            text = path.read_text(encoding="utf-8")
            self.assertIn("target: github-copilot", text, name)
            self.assertIn(".github/copilot-instructions.md", text, name)
            for phrase in phrases:
                self.assertIn(phrase, text, name)
        governance = json.loads(
            (ROOT / "governance" / "sovara_fcx_copilot_pro_adapter_v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual("DENY", governance["credit_policy"]["paid_overage_default"])
        self.assertEqual("PRIVATE_ACCOUNT_EVIDENCE_REQUIRED", governance["account_entitlement"])


if __name__ == "__main__":
    unittest.main()
