from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from phoenix.workflow_freeze_convergence import (
    build_receipt,
    canonical_sha256,
    required_from_policy,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phoenix-emergency-freeze.yml"
POLICY = ROOT / "governance" / "github_airlock_policy.json"
NOW = datetime(2026, 8, 5, 3, 0, tzinfo=timezone.utc)
PROVIDER_GATEWAY = ".github/workflows/sovara-litellm-v2-3-provider-admission.yml"
CIOS_GATEWAY = ".github/workflows/cios-production-lane.yml"
MATURATION_SHADOW = ".github/workflows/superior-logic-maturation-shadow.yml"
REQUIRED = sorted(required_from_policy(POLICY))


def row(index: int, path: str, state: str = "active"):
    return {"id": index, "path": path, "state": state, "name": path}


def required(state: str = "active", attempt: int = 1):
    return [
        {"id": index, "path": path, "state": state, "attempt": attempt}
        for index, path in enumerate(REQUIRED, start=1)
    ]


class FreezeConvergenceTests(unittest.TestCase):
    def receipt(self, **overrides):
        values = dict(
            repository="mosianekk-lang/Federation-Omega",
            source_sha="a" * 40,
            run_id=123,
            run_attempt=1,
            required_workflows=REQUIRED,
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

    def test_required_set_is_loaded_from_airlock_policy(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(set(policy["active_workflow_allowlist"]), set(REQUIRED))
        self.assertEqual(
            set(policy["execution_quarantine"]["keep_active"]), set(REQUIRED)
        )
        self.assertIn(MATURATION_SHADOW, REQUIRED)

    def test_policy_drift_fails_closed(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        policy["execution_quarantine"]["keep_active"] = [
            path for path in policy["execution_quarantine"]["keep_active"]
            if path != MATURATION_SHADOW
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "AIRLOCK_POLICY_WORKFLOW_SET_DRIFT"):
                required_from_policy(path)

    def test_individual_readback_overrides_eventually_consistent_list_omission(self):
        result = self.receipt()
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual([], result["missing_required"])
        self.assertEqual(
            "POLICY_DERIVED_INDIVIDUAL_WORKFLOW_ENDPOINT_BOUNDED_CONVERGENCE",
            result["required_workflow_readback_method"],
        )
        self.assertEqual("governance/github_airlock_policy.json", result["workflow_policy_authority"])

    def test_missing_individual_required_state_fails(self):
        values = required()
        values[1]["state"] = "disabled_manually"
        result = self.receipt(required_readback=values)
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual([REQUIRED[1]], result["missing_required"])

    def test_maturation_shadow_disabled_state_fails_convergence(self):
        values = required()
        index = REQUIRED.index(MATURATION_SHADOW)
        values[index]["state"] = "disabled_manually"
        result = self.receipt(required_readback=values)
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual([MATURATION_SHADOW], result["missing_required"])

    def test_provider_gateway_disabled_state_fails_convergence(self):
        values = required()
        provider_index = REQUIRED.index(PROVIDER_GATEWAY)
        values[provider_index]["state"] = "disabled_manually"
        result = self.receipt(required_readback=values)
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual([PROVIDER_GATEWAY], result["missing_required"])

    def test_required_workflows_are_not_unexpected(self):
        result = self.receipt(
            after=[
                row(1, REQUIRED[0]),
                row(99, PROVIDER_GATEWAY),
                row(100, CIOS_GATEWAY),
                row(101, MATURATION_SHADOW),
            ]
        )
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual([], result["unexpected_active"])
        self.assertIn(MATURATION_SHADOW, result["required_active_workflows"])

    def test_unexpected_required_readback_fails_closed(self):
        values = required()
        values.append(
            {
                "id": 999,
                "path": ".github/workflows/not-in-policy.yml",
                "state": "active",
                "attempt": 1,
            }
        )
        result = self.receipt(required_readback=values)
        self.assertEqual("READBACK_FAILED", result["status"])
        self.assertEqual(
            [".github/workflows/not-in-policy.yml"],
            result["unexpected_required_readback"],
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

    def test_workflow_derives_required_workflows_from_policy(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("policy_path='governance/github_airlock_policy.json'", text)
        self.assertIn("jq -r '.active_workflow_allowlist[]'", text)
        self.assertIn("mapfile -t required_paths", text)
        self.assertIn('--policy "${policy_path}"', text)
        self.assertNotIn("required_specs=(", text)

    def test_workflow_fail_closes_on_policy_projection_drift(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(".active_workflow_allowlist | sort", text)
        self.assertIn(".execution_quarantine.keep_active | sort", text)
        self.assertIn(
            "Airlock active-workflow policy and execution-quarantine keep-active set are missing or divergent",
            text,
        )

    def test_workflow_dispatches_reenabled_maturation_shadow_canary(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            '"superior-logic-maturation-shadow.yml|.github/workflows/superior-logic-maturation-shadow.yml|Superior Logic maturation shadow"',
            text,
        )

    def test_provider_specific_reenable_dispatch_is_preserved(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            '"pfrd-omega-operator-auth-probe.yml|.github/workflows/pfrd-omega-operator-auth-probe.yml|operator auth probe"',
            text,
        )
        self.assertIn(
            '"sovara-litellm-v2-3-provider-admission.yml|.github/workflows/sovara-litellm-v2-3-provider-admission.yml|LiteLLM provider admission"',
            text,
        )
        self.assertIn(
            '"/repos/${GITHUB_REPOSITORY}/actions/workflows/${workflow_file}/dispatches"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
