from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "source_provenance", ROOT / "phoenix" / "source_provenance.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SourceProvenanceTests(unittest.TestCase):
    def test_all_pr_associated_commits_verify(self):
        report = MODULE.build_report(
            "owner/repo",
            "b" * 40,
            [
                {"sha": "a" * 40, "associated_pr_count": 1},
                {"sha": "b" * 40, "associated_pr_count": 2},
            ],
        )
        self.assertEqual("VERIFIED", report["status"])
        self.assertEqual(0, report["unadmitted_commit_count"])

    def test_direct_commit_fails_provenance(self):
        direct = "c" * 40
        report = MODULE.build_report(
            "owner/repo",
            direct,
            [{"sha": direct, "associated_pr_count": 0}],
        )
        self.assertEqual("UNADMITTED_HISTORY", report["status"])
        self.assertEqual([direct], report["unadmitted_commits"])

    def test_empty_input_fails_closed(self):
        report = MODULE.build_report("owner/repo", "d" * 40, [])
        self.assertEqual("UNADMITTED_HISTORY", report["status"])

    def test_agent_governance_contract_is_present_and_fail_closed(self):
        agent_contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        copilot_contract = (
            ROOT / ".github" / "copilot-instructions.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "Never commit or push directly to `main`.",
            "New workflows are default-deny.",
            "Do not commit generated runtime receipts",
            "require exact provider readback",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, agent_contract)
        for phrase in (
            "Follow the root `AGENTS.md` governance contract",
            "commit or push directly to `main`",
            "Runtime outputs belong in immutable artifacts",
            "merge-result readback",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, copilot_contract)
        self.assertIn("provider protection is not yet active", copilot_contract)
        self.assertNotIn("branch protection is active", agent_contract.lower())

    def test_main_airlock_ruleset_is_sole_owner_safe_and_requires_admission(self):
        ruleset = json.loads(
            (
                ROOT
                / "governance"
                / "federation_omega_main_airlock.ruleset.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual("active", ruleset["enforcement"])
        self.assertEqual([], ruleset["bypass_actors"])
        by_type = {rule["type"]: rule for rule in ruleset["rules"]}
        pull_request = by_type["pull_request"]["parameters"]
        self.assertEqual(0, pull_request["required_approving_review_count"])
        self.assertFalse(pull_request["require_code_owner_review"])
        self.assertFalse(pull_request["require_last_push_approval"])
        self.assertTrue(pull_request["required_review_thread_resolution"])
        checks = by_type["required_status_checks"]["parameters"]
        self.assertTrue(checks["strict_required_status_checks_policy"])
        self.assertEqual(
            [{"context": "admission"}], checks["required_status_checks"]
        )


if __name__ == "__main__":
    unittest.main()
