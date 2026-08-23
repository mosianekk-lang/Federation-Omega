from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from phoenix.workflow_freeze_convergence import build_receipt, canonical_sha256

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
NOW = datetime(2026, 8, 5, 3, 0, tzinfo=timezone.utc)
REQUIRED = [
    ".github/workflows/github-airlock.yml",
    ".github/workflows/public-repository-leak-guard.yml",
    ".github/workflows/phoenix-emergency-freeze.yml",
    ".github/workflows/bubbles-command-bus.yml",
    ".github/workflows/bubbles-provider-authority-recovery-probe.yml",
]


def row(index: int, path: str, state: str = "active"):
    return {"id": index, "path": path, "state": state, "name": path}


def required(state: str = "active", attempt: int = 1):
    return [
        {"id": index, "path": path, "state": state, "attempt": attempt}
        for index, path in enumerate(REQUIRED, start=1)
    ]


def set_required_state(rows, path: str, state: str):
    for item in rows:
        if item["path"] == path:
            item["state"] = state
            return rows
    raise AssertionError(f"required workflow not found in fixture: {path}")


class FreezeConvergenceTests(unittest.TestCase):
    def receipt(self, **overrides):
        values = dict(
            repository="mosianekk-lang/Federation-Omega",
            source_sha="a" * 40,
            run_id=123,
            run_attempt=1,
            before=[row(index, path) for index, path in enumerate(REQUIRED, start=1)],
            after=[row(1, REQUIRED[0])],
            required_readback=required(),
            disabled=[],
            enabled=[],
            errors=[],
            recorded_at=NOW,
        )
        values.update(overrides)
        return build_receipt(**values)

    def test_individual_readback_overrides_eventually_consistent_list_omission(self):
        result = self.receipt()
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual([], result["missing_required"])
        self.assertEqual(
            "INDIVIDUAL_WORKFLOW_ENDPOINT_BOUNDED_CONVERGENCE",
            result["required_workflow_readback_method"],
        )

    def test_missing_individual_required_state_fails(self):
        values = required()
        set_required_state(
            values,
            ".github/workflows/public-repository-leak-guard.yml",
            "disabled_manually",
        )
        result = self.receipt(required_readback=values)
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual(
            [".github/workflows/public-repository-leak-guard.yml"],
            result["missing_required"],
        )

    def test_bubbles_disabled_state_fails_convergence(self):
        values = required()
        set_required_state(
            values,
            ".github/workflows/bubbles-command-bus.yml",
            "disabled_manually",
        )
        result = self.receipt(required_readback=values)
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual(
            [".github/workflows/bubbles-command-bus.yml"],
            result["missing_required"],
        )

    def test_provider_authority_recovery_probe_disabled_state_fails_convergence(self):
        values = required()
        set_required_state(
            values,
            ".github/workflows/bubbles-provider-authority-recovery-probe.yml",
            "disabled_manually",
        )
        result = self.receipt(required_readback=values)
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual(
            [".github/workflows/bubbles-provider-authority-recovery-probe.yml"],
            result["missing_required"],
        )

    def test_unexpected_active_workflow_still_fails(self):
        result = self.receipt(
            after=[row(1, REQUIRED[0]), row(99, ".github/workflows/legacy.yml")]
        )
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual([".github/workflows/legacy.yml"], result["unexpected_active"])

    def test_provider_managed_workflow_is_allowlisted(self):
        result = self.receipt(
            after=[
                row(1, REQUIRED[0]),
                row(99, "dynamic/dependabot/dependabot-updates"),
            ]
        )
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual(
            ["dynamic/dependabot/dependabot-updates"],
            result["provider_managed_active"],
        )

    def test_permanent_errors_fail_closed(self):
        result = self.receipt(errors=["Failed to disable legacy workflow"])
        self.assertEqual("READBACK_FAILED", result["status"])

    def test_receipt_hash_is_bound(self):
        result = self.receipt()
        claimed = result.pop("receipt_sha256")
        self.assertEqual(claimed, canonical_sha256(result))

    def test_max_attempt_is_preserved(self):
        result = self.receipt(required_readback=required(attempt=4))
        self.assertEqual(4, result["convergence_attempt_count"])

    def test_no_source_mutation_claim(self):
        result = self.receipt()
        self.assertFalse(result["source_mutation_attempted"])

    def test_workflow_uses_unambiguous_empty_json_fallback(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("${payload:-{}}", text)
        self.assertIn('if [[ -z "${payload}" ]]; then', text)
        self.assertIn("payload='{}'", text)
        self.assertIn('<<< "${payload}"', text)

    def test_workflow_treats_bubbles_command_bus_as_required_active(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("bubbles-command-bus.yml"), 2)
        self.assertIn(
            '"bubbles-command-bus.yml|.github/workflows/bubbles-command-bus.yml"',
            text,
        )

    def test_workflow_treats_provider_authority_recovery_probe_as_required_active(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            text.count("bubbles-provider-authority-recovery-probe.yml"),
            2,
        )
        self.assertIn(
            '"bubbles-provider-authority-recovery-probe.yml|.github/workflows/'
            'bubbles-provider-authority-recovery-probe.yml"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
