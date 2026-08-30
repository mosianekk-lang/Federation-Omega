from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fcx-copilot-falsifier-canary.yml"
POLICY_PATH = ROOT / "governance" / "github_airlock_policy.json"
AIRLOCK_SPEC = importlib.util.spec_from_file_location(
    "github_airlock_fcx_gateway", ROOT / "tools" / "github_airlock.py"
)
assert AIRLOCK_SPEC and AIRLOCK_SPEC.loader
AIRLOCK = importlib.util.module_from_spec(AIRLOCK_SPEC)
sys.modules[AIRLOCK_SPEC.name] = AIRLOCK
AIRLOCK_SPEC.loader.exec_module(AIRLOCK)


class FCXCopilotActionsGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_gateway_is_airlock_allowlisted_and_manual_only(self) -> None:
        path = ".github/workflows/fcx-copilot-falsifier-canary.yml"
        self.assertIn(path, self.policy["active_workflow_allowlist"])
        self.assertEqual(["workflow_dispatch"], self.policy["allowed_events"][path])
        self.assertIn(path, self.policy["execution_quarantine"]["keep_active"])
        findings = AIRLOCK.analyse_workflow(path, self.text, self.policy)
        self.assertEqual([], findings)
        self.assertNotRegex(self.text, r"(?m)^\s{0,4}(push|pull_request|schedule|issues|repository_dispatch)\s*:")

    def test_copilot_requests_write_is_default_deny_except_exact_gateway(self) -> None:
        allowed = set(self.policy.get("copilot_requests_write_workflow_allowlist", []))
        self.assertEqual({".github/workflows/fcx-copilot-falsifier-canary.yml"}, allowed)
        observed: set[str] = set()
        for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?mi)^\s*copilot-requests\s*:\s*write\s*$", text):
                observed.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(allowed, observed)

    def test_gateway_has_no_repository_or_identity_escalation(self) -> None:
        self.assertRegex(self.text, r"(?mi)^\s*contents\s*:\s*read\s*$")
        self.assertRegex(self.text, r"(?mi)^\s*copilot-requests\s*:\s*write\s*$")
        self.assertNotRegex(self.text, r"(?mi)^\s*contents\s*:\s*write\s*$")
        self.assertNotRegex(self.text, r"(?mi)^\s*id-token\s*:\s*write\s*$")
        self.assertNotRegex(self.text, r"(?mi)^\s*actions\s*:\s*write\s*$")
        self.assertNotRegex(self.text, r"(?mi)^\s*statuses\s*:\s*write\s*$")
        self.assertNotIn("git push", self.text.lower())
        self.assertNotIn("gh api --method", self.text.lower())

    def test_gateway_is_pinned_to_frozen_pr810_target_and_prompt(self) -> None:
        self.assertIn("TARGET_PR: '810'", self.text)
        self.assertIn("TARGET_BASE_SHA: 'a202c105217ad774083b0234ec7561299900bbc3'", self.text)
        self.assertIn("TARGET_HEAD_SHA: '57717da12451ae0b58b3ce92cfad77782844376b'", self.text)
        self.assertIn("COPILOT_MODEL: 'gpt-5.6-luna'", self.text)
        self.assertIn("MAX_AI_CREDITS: '30'", self.text)
        self.assertIn(
            "PROMPT_SHA256: 'b768c73bc97fe4c553cac76b91449bc636180eddab3171e450cd7818a315cc7f'",
            self.text,
        )
        self.assertIn("default: false", self.text)
        self.assertIn("if: ${{ inputs.execute == true }}", self.text)

    def test_copilot_tool_surface_is_read_only_and_no_mcp_web(self) -> None:
        self.assertIn("--available-tools='view,grep,glob'", self.text)
        self.assertIn("--allow-tool='read'", self.text)
        self.assertIn("--deny-tool='write'", self.text)
        self.assertIn("--disable-builtin-mcps", self.text)
        self.assertNotIn("--allow-all", self.text)
        self.assertNotIn("--yolo", self.text)
        self.assertNotIn("--allow-all-urls", self.text)

    def test_session_limit_is_explicitly_soft_and_requires_usage_readback(self) -> None:
        self.assertIn("--max-ai-credits=\"$MAX_AI_CREDITS\"", self.text)
        self.assertIn("'provider_usage_readback_required': True", self.text)
        self.assertIn("'observed_model_identity_required': True", self.text)
        self.assertIn("'promotion_claimed': False", self.text)

    def test_checkout_and_artifact_actions_are_immutably_pinned(self) -> None:
        findings = AIRLOCK.action_reference_findings(
            ".github/workflows/fcx-copilot-falsifier-canary.yml",
            self.text,
        )
        self.assertEqual([], findings)
        self.assertIn("persist-credentials: false", self.text)

    def test_private_baseline_answers_are_not_committed(self) -> None:
        forbidden = (
            "hardcoded export-policy 1.0.20",
            "direct per-file Python diagnostic",
            "ModuleNotFoundError noise",
            "primary baseline defect",
        )
        lowered = self.text.lower()
        for phrase in forbidden:
            self.assertNotIn(phrase.lower(), lowered)


if __name__ == "__main__":
    unittest.main()
