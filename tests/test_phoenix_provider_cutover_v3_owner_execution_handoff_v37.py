from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "phoenix" / "ops-template" / "owner_execution_handoff.py"
SPEC = importlib.util.spec_from_file_location("owner_execution_handoff_v37", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

RELEASE = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_attested_authorization_release_receipt_v36.json"
)
CONTRACT = (
    ROOT
    / "phoenix"
    / "ops-template"
    / "governance"
    / "OWNER_EXECUTION_HANDOFF_CONTRACT.json"
)
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_handoff_checkpoint_v37.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v37.json"
POLICY = ROOT / "phoenix" / "export_policy.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rehash(payload: dict, field: str) -> dict:
    body = dict(payload)
    body.pop(field, None)
    body[field] = MODULE.canonical_sha256(body)
    return body


class OwnerExecutionHandoffV37Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = load(RELEASE)
        self.now = datetime(2026, 8, 5, 7, 31, tzinfo=timezone.utc)

    def build(self):
        return MODULE.build_handoff(
            release_receipt=self.release,
            current_source_sha="cf983f6244a33a9ba522a0ae2ab9eca69b9666dc",
            owner_login="mosianekk-lang",
            repository_full_name="mosianekk-lang/Federation-Omega",
            owner_packet_sha256=self.release["provider_proof"]["owner_packet_sha256"],
            generated_at=self.now,
        )

    def test_valid_handoff_is_ordered_hash_bound_and_non_executing(self):
        result = self.build()
        self.assertEqual(
            "OWNER_EXECUTION_HANDOFF_VERIFIED_NO_OWNER_ACTION_PERFORMED",
            result["status"],
        )
        self.assertEqual(list(range(1, 12)), [step["sequence"] for step in result["ordered_steps"]])
        self.assertEqual([2, 4, 7, 10], result["owner_reserved_steps"])
        self.assertFalse(result["owner_action_performed"])
        self.assertFalse(result["provider_request_performed"])
        self.assertFalse(result["provider_apply_performed"])
        self.assertFalse(result["authorization_consumption_state_created"])
        self.assertFalse(result["external_communication_performed"])
        claimed = result["handoff_sha256"]
        body = dict(result)
        body.pop("handoff_sha256")
        self.assertEqual(claimed, MODULE.canonical_sha256(body))

    def test_tampered_commercial_truth_fails_closed(self):
        self.release["commercial_truth"]["verified_live_revenue_events"] = 1
        self.release = rehash(self.release, "receipt_sha256")
        with self.assertRaises(MODULE.OwnerExecutionHandoffError):
            self.build()

    def test_provider_apply_overclaim_fails_closed(self):
        self.release["provider_proof"]["provider_apply_performed"] = True
        self.release = rehash(self.release, "receipt_sha256")
        with self.assertRaises(MODULE.OwnerExecutionHandoffError):
            self.build()

    def test_owner_repository_mismatch_fails_closed(self):
        with self.assertRaises(MODULE.OwnerExecutionHandoffError):
            MODULE.build_handoff(
                release_receipt=self.release,
                current_source_sha="cf983f6244a33a9ba522a0ae2ab9eca69b9666dc",
                owner_login="different-owner",
                repository_full_name="mosianekk-lang/Federation-Omega",
                owner_packet_sha256=self.release["provider_proof"]["owner_packet_sha256"],
                generated_at=self.now,
            )

    def test_invalid_packet_hash_fails_closed(self):
        with self.assertRaises(MODULE.OwnerExecutionHandoffError):
            MODULE.build_handoff(
                release_receipt=self.release,
                current_source_sha="cf983f6244a33a9ba522a0ae2ab9eca69b9666dc",
                owner_login="mosianekk-lang",
                repository_full_name="mosianekk-lang/Federation-Omega",
                owner_packet_sha256="not-a-sha256",
                generated_at=self.now,
            )

    def test_contract_checkpoint_projection_and_export_truth(self):
        contract = load(CONTRACT)
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        policy = load(POLICY)

        MODULE._verify_self_hash(checkpoint, field="checkpoint_sha256", label="checkpoint")
        MODULE._verify_self_hash(projection, field="projection_sha256", label="projection")
        self.assertEqual("PREPARED_NOT_EXECUTED_OWNER_RESERVED", contract["status"])
        self.assertFalse(contract["controls"]["owner_action_performed"])
        self.assertFalse(contract["controls"]["provider_apply_performed"])
        self.assertEqual(
            "OWNER_EXECUTION_HANDOFF_IMPLEMENTED_PROVIDER_PROOF_REQUIRED_"
            "OWNER_ACTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED",
            checkpoint["status"],
        )
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        required = set(policy["ops"]["required_files"])
        self.assertIn("owner_execution_handoff.py", required)
        self.assertIn("governance/OWNER_EXECUTION_HANDOFF_CONTRACT.json", required)


if __name__ == "__main__":
    unittest.main()
