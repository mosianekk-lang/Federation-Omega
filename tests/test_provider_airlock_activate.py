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


def activation_state() -> dict:
    return json.loads(
        (ROOT / "governance" / "provider_airlock_activation_state.json").read_text(
            encoding="utf-8"
        )
    )


class ProviderAirlockActivatorTests(unittest.TestCase):
    def test_canonical_ruleset_is_fail_closed_and_complete(self):
        payload = ruleset()
        self.assertIs(payload, MODULE.validate_ruleset(payload))
        self.assertEqual([], payload["bypass_actors"])
        self.assertEqual(["~DEFAULT_BRANCH"], payload["conditions"]["ref_name"]["include"])
        self.assertEqual([], payload["conditions"]["ref_name"]["exclude"])
        by_type = {item["type"]: item for item in payload["rules"]}
        self.assertTrue(MODULE.EXPECTED_RULE_TYPES.issubset(by_type))
        pull_request = by_type["pull_request"]["parameters"]
        self.assertEqual(0, pull_request["required_approving_review_count"])
        self.assertFalse(pull_request["require_code_owner_review"])
        self.assertFalse(pull_request["require_last_push_approval"])
        self.assertTrue(pull_request["required_review_thread_resolution"])
        checks = by_type["required_status_checks"]["parameters"]
        self.assertTrue(checks["strict_required_status_checks_policy"])
        self.assertEqual(
            [{"context": "admission"}, {"context": "contract"}, {"context": "scan"}],
            checks["required_status_checks"],
        )
        self.assertEqual(("admission", "contract", "scan"), MODULE.REQUIRED_STATUS_CONTEXTS)

    def test_authority_or_release_court_dilution_is_rejected(self):
        payload = ruleset()
        payload["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole"}]
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)

        payload = ruleset()
        next(item for item in payload["rules"] if item["type"] == "pull_request")[
            "parameters"
        ]["required_approving_review_count"] = 1
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)

        payload = ruleset()
        status = next(
            item for item in payload["rules"] if item["type"] == "required_status_checks"
        )["parameters"]
        status["required_status_checks"] = [{"context": "admission"}]
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)

        payload = ruleset()
        status = next(
            item for item in payload["rules"] if item["type"] == "required_status_checks"
        )["parameters"]
        status["strict_required_status_checks_policy"] = False
        with self.assertRaises(MODULE.ActivationError):
            MODULE.validate_ruleset(payload)

    def test_negative_canary_payload_is_scoped_away_from_main(self):
        desired = ruleset()
        canary = MODULE.canary_ruleset(desired, "phoenix-ruleset-canary-abc123")
        self.assertEqual(
            ["refs/heads/phoenix-ruleset-canary-abc123"],
            canary["conditions"]["ref_name"]["include"],
        )
        self.assertEqual([], canary["conditions"]["ref_name"]["exclude"])
        self.assertEqual(["~DEFAULT_BRANCH"], desired["conditions"]["ref_name"]["include"])
        self.assertNotEqual(desired["name"], canary["name"])

    def test_provider_metadata_cannot_change_exact_ruleset_comparison(self):
        desired = ruleset()
        actual = json.loads(json.dumps(desired))
        actual.update({"id": 42, "source_type": "Repository", "node_id": "RRS_abc"})
        self.assertEqual(
            MODULE.canonical_ruleset_view(desired),
            MODULE.canonical_ruleset_view(actual),
        )

    def test_dry_run_receipt_is_hash_bound_and_contains_no_credential_value(self):
        payload = {
            "schema": "FEDOMEGA-PROVIDER-AIRLOCK-ACTIVATION-1",
            "status": "DRY_RUN_VERIFIED",
            "credential_source_env": "GH_ADMIN_TOKEN",
            "credential_value_recorded": False,
            "main_mutation_attempted": False,
            "required_status_contexts": list(MODULE.REQUIRED_STATUS_CONTEXTS),
        }
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "receipt.json"
            MODULE.write_receipt(target, payload)
            saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertFalse(saved["credential_value_recorded"])
        self.assertFalse(saved["main_mutation_attempted"])
        self.assertEqual(["admission", "contract", "scan"], saved["required_status_contexts"])
        self.assertEqual(64, len(saved["receipt_sha256"]))
        sanitized = json.dumps(saved).lower().replace("gh_admin_token", "")
        self.assertNotIn("bearer ", sanitized)
        self.assertNotIn("github_pat_", sanitized)
        self.assertNotIn("ghp_", sanitized)

    def test_activation_state_preserves_absence_and_direct_write_incident(self):
        state = activation_state()
        self.assertEqual("FEDOMEGA-PROVIDER-AIRLOCK-ACTIVATION-STATE-1", state["schema"])

        authority = state["connected_authority"]
        self.assertTrue(authority["repository_admin_standing_reported"])
        self.assertFalse(authority["connector_ruleset_mutation_exposed"])
        self.assertFalse(authority["connector_branch_protection_mutation_exposed"])

        observed = state["provider_observation"]
        self.assertEqual("READ_ONLY", observed["observation_mode"])
        self.assertFalse(observed["main_protected"])
        self.assertFalse(observed["branch_protection_enabled"])
        self.assertEqual("off", observed["required_status_checks_enforcement_level"])
        self.assertEqual([], observed["required_status_contexts"])
        self.assertEqual(0, observed["ruleset_count"])
        self.assertEqual([], observed["rulesets"])

        provider = state["provider_state"]
        self.assertFalse(provider["provider_apply_performed"])
        self.assertEqual("ABSENT", provider["provider_receipt_status"])
        self.assertEqual("ABSENT_PROVIDER_READBACK", provider["main_ruleset_active"])
        self.assertEqual([], provider["required_status_contexts_active"])
        self.assertEqual("NOT_RUN", provider["direct_update_rejection_canary"])

        incident = state["source_incident"]
        self.assertEqual("INC-FEDOMEGA-DIRECT-MAIN-20260830-001", incident["incident_id"])
        self.assertEqual("tmp", incident["unintended_path"])
        self.assertEqual(0, incident["unintended_path_content_bytes"])
        self.assertFalse(incident["history_rewritten"])
        self.assertFalse(incident["force_main_ref_update_performed"])
        self.assertFalse(incident["repair_effect_on_main"])
        self.assertTrue(incident.get("prospective_repair_tree_tmp_absent", False))

        defence = state["local_defence_in_depth"]
        self.assertEqual("ABSENT", defence["provider_prevention"])
        self.assertIn("NOT_PROVIDER_ENFORCED", defence["agent_governance_contract"])

        gate = state["verification_gate"]
        self.assertEqual("FEDOMEGA-PROVIDER-AIRLOCK-ACTIVATION-1", gate["required_receipt_schema"])
        self.assertEqual("VERIFIED", gate["required_receipt_status"])
        required = set(gate["required_checks"])
        self.assertTrue(
            {
                "source_repair.tmp_absent_on_admitted_main",
                "source_repair.current_main_airlock_bubbles_leakguard_green",
                "negative_canary.direct_update_rejected",
                "provider_readback.ruleset_exact",
                "provider_readback.required_status_contexts_exact",
                "provider_readback.main_sha_unchanged",
            }.issubset(required)
        )
        truth = state["truth_boundary"].lower()
        self.assertIn("provider prevention is absent", truth)
        self.assertNotIn("provider prevention is active", truth)

    def test_verified_state_cannot_exist_without_provider_receipt_and_negative_canary(self):
        state = activation_state()
        if state.get("state") == "VERIFIED":
            provider = state["provider_state"]
            self.assertTrue(provider["provider_apply_performed"])
            self.assertEqual("VERIFIED", provider["provider_receipt_status"])
            self.assertEqual("VERIFIED", provider["main_ruleset_active"])
            self.assertEqual("REJECTED", provider["direct_update_rejection_canary"])
            receipt_sha = provider.get("provider_receipt_sha256")
            self.assertIsInstance(receipt_sha, str)
            self.assertEqual(64, len(receipt_sha))


if __name__ == "__main__":
    unittest.main()
