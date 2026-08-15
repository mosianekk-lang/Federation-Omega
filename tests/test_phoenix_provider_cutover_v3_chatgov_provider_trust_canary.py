from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bubbles.chat_governor_omega3.provider_trust_canary import run_canary
from federation_consolidation.provider_trust_resolver import EVIDENCE_SCHEMA, resolve_provider_trust


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "governance/provider_trust_contract_v1.json").read_text())


def live_resolution() -> dict:
    return resolve_provider_trust(
        CONTRACT,
        {
            "schema": EVIDENCE_SCHEMA,
            "capability_alias": "OPENAI_PRIMARY_RUNTIME",
            "binding_id": "FEDOMEGA_GITHUB_ACTIONS_OPENAI_PRIMARY",
            "credential_reference_found": True,
            "runtime_bound": True,
            "provider_authenticated": True,
            "provider_live_verified": True,
            "provider_error_code": None,
            "semantic_receipt_sha256": "a" * 64,
            "archive_readback_verified": True,
            "archive_sha256": "b" * 64,
            "outer_workflow_success": True,
            "secret_value_recorded": False,
        },
    )


def billing_resolution() -> dict:
    return resolve_provider_trust(
        CONTRACT,
        {
            "schema": EVIDENCE_SCHEMA,
            "capability_alias": "OPENAI_PRIMARY_RUNTIME",
            "binding_id": "FEDOMEGA_GITHUB_ACTIONS_OPENAI_PRIMARY",
            "credential_reference_found": True,
            "runtime_bound": True,
            "provider_authenticated": True,
            "provider_live_verified": False,
            "provider_error_code": "credit_balance_exhausted",
            "semantic_receipt_sha256": None,
            "archive_readback_verified": False,
            "archive_sha256": None,
            "outer_workflow_success": True,
            "secret_value_recorded": False,
        },
    )


class ChatGovProviderTrustCanaryTests(unittest.TestCase):
    def run_with(self, resolution: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resolution_path = root / "provider-trust-resolution.json"
            resolution_path.write_text(json.dumps(resolution), encoding="utf-8")
            return run_canary(
                resolution_path=resolution_path,
                db_path=root / "chatgov.sqlite3",
            )

    def test_live_shared_trust_receipt_suppresses_owner_prompt(self):
        receipt = self.run_with(live_resolution())
        self.assertEqual(receipt["state"], "CHATGOV_PROVIDER_TRUST_RECEIVING_HOME_VERIFIED")
        self.assertTrue(receipt["provider_runtime_ready"])
        self.assertTrue(receipt["pre_user_prompt_reconciled"])
        self.assertTrue(receipt["owner_prompt_suppressed"])
        self.assertTrue(receipt["checkpoint_readback_verified"])
        self.assertTrue(receipt["proof_bearing"])
        self.assertFalse(receipt["consequential_authority_granted"])
        self.assertFalse(receipt["provider_call_attempted"])
        self.assertFalse(receipt["secret_values_recorded"])
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

    def test_non_live_billing_receipt_cannot_fake_success(self):
        receipt = self.run_with(billing_resolution())
        self.assertEqual(receipt["state"], "CHATGOV_PROVIDER_TRUST_RECEIVING_HOME_FAILED")
        self.assertFalse(receipt["provider_runtime_ready"])
        self.assertFalse(receipt["owner_prompt_suppressed"])
        self.assertFalse(receipt["credential_rotation_recommended"])
        self.assertEqual(receipt["next_action"], "RESTORE_PROVIDER_BILLING")
        self.assertFalse(receipt["consequential_authority_granted"])


if __name__ == "__main__":
    unittest.main()
