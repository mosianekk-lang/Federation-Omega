from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "provider_airlock_activate", ROOT / "phoenix" / "provider_airlock_activate.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def ruleset() -> dict:
    return json.loads(
        (ROOT / "governance" / "federation_omega_main_airlock.ruleset.json").read_text(
            encoding="utf-8"
        )
    )


class ProviderAirlockActivatorTests(unittest.TestCase):
    def test_canonical_ruleset_passes_validation(self):
        payload = ruleset()
        self.assertIs(payload, MODULE.validate_ruleset(payload))

    def test_approval_or_bypass_dilution_is_rejected(self):
        payload = ruleset()
        payload["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole"}]
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)
        payload = ruleset()
        for rule in payload["rules"]:
            if rule["type"] == "pull_request":
                rule["parameters"]["required_approving_review_count"] = 1
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)

    def test_missing_or_non_strict_admission_is_rejected(self):
        payload = ruleset()
        for rule in payload["rules"]:
            if rule["type"] == "required_status_checks":
                rule["parameters"]["required_status_checks"] = [{"context": "other"}]
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)
        payload = ruleset()
        for rule in payload["rules"]:
            if rule["type"] == "required_status_checks":
                rule["parameters"]["strict_required_status_checks_policy"] = False
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)

    def test_canary_targets_only_temporary_branch(self):
        desired = ruleset()
        canary = MODULE.canary_ruleset(desired, "phoenix-ruleset-canary-abc123")
        self.assertEqual(
            ["refs/heads/phoenix-ruleset-canary-abc123"],
            canary["conditions"]["ref_name"]["include"],
        )
        self.assertEqual(["~DEFAULT_BRANCH"], desired["conditions"]["ref_name"]["include"])
        self.assertNotEqual(desired["name"], canary["name"])

    def test_provider_metadata_does_not_affect_exact_comparison(self):
        desired = ruleset()
        actual = json.loads(json.dumps(desired))
        actual.update({"id": 42, "source_type": "Repository", "node_id": "RRS_abc"})
        self.assertEqual(
            MODULE.canonical_ruleset_view(desired),
            MODULE.canonical_ruleset_view(actual),
        )

    def test_dry_run_receipt_records_no_credential(self):
        payload = {
            "schema": "FEDOMEGA-PROVIDER-AIRLOCK-ACTIVATION-1",
            "status": "DRY_RUN_VERIFIED",
            "credential_source_env": "GH_ADMIN_TOKEN",
            "credential_value_recorded": False,
            "main_mutation_attempted": False,
        }
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "receipt.json"
            MODULE.write_receipt(target, payload)
            saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertFalse(saved["credential_value_recorded"])
        self.assertNotIn("token", json.dumps(saved).lower().replace("gh_admin_token", ""))
        self.assertEqual(64, len(saved["receipt_sha256"]))


if __name__ == "__main__":
    unittest.main()
