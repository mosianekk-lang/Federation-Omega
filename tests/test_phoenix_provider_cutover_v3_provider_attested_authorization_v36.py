from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "phoenix" / "ops-template" / "provider_attested_authorization.py"
SPEC = importlib.util.spec_from_file_location("provider_attested_authorization_v36", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CONTRACT = (
    ROOT
    / "phoenix"
    / "ops-template"
    / "governance"
    / "PROVIDER_ATTESTED_AUTHORIZATION_CONTRACT.json"
)
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_attested_authorization_checkpoint_v36.json"
)
PROJECTION = (
    ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v36.json"
)
POLICY = ROOT / "phoenix" / "export_policy.json"


def self_hash(payload: dict, field: str) -> dict:
    body = dict(payload)
    body[field] = MODULE.canonical_sha256(payload)
    return body


class ProviderAttestedAuthorizationV36Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 5, 7, 5, tzinfo=timezone.utc)
        self.identity = self_hash(
            {
                "schema": MODULE.IDENTITY_RECEIPT_SCHEMA,
                "status": "PROVIDER_NATIVE_OWNER_IDENTITY_VERIFIED",
                "capture_mode": "PROVIDER_NATIVE",
                "owner_login": "mosianekk-lang",
                "repository_full_name": "mosianekk-lang/Federation-Omega",
                "comment_id": 123456789,
                "verified_at": "2026-08-05T07:04:00Z",
                "owner_identity_authenticity_proven": True,
                "provider_native_attestation_readback_present": True,
                "owner_execution_present": True,
                "owner_attestation_present": True,
                "owner_authorization_present": False,
                "provider_authority_created": False,
                "provider_apply_performed": False,
                "external_commercial_gate_advanced": False,
                "credential_value_recorded": False,
            },
            "receipt_sha256",
        )
        self.authority = self_hash(
            {
                "schema": "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-RECEIPT-1",
                "provider": "github",
                "status": "PROVIDER_AUTHORITY_VERIFIED",
                "observed_at": "2026-08-05T07:04:30Z",
                "route": {
                    "authority_mode": "USER_SCOPED_ADMIN",
                    "repository_creation_endpoint": "https://api.github.com/user/repos",
                },
                "credential_value_recorded": False,
                "provider_apply_performed": False,
            },
            "receipt_sha256",
        )
        decision_body = {
            "schema": MODULE.DECISION_SCHEMA,
            "status": "AUTHORIZED_APPLY",
            "issued_at": "2026-08-05T07:04:45Z",
            "expires_at": "2026-08-05T07:09:45Z",
            "provider_identity_receipt_sha256": self.identity["receipt_sha256"],
            "provider_authority_receipt_sha256": self.authority["receipt_sha256"],
            "owner_login": "mosianekk-lang",
            "repository_full_name": "mosianekk-lang/Federation-Omega",
            "comment_id": 123456789,
            "authority_mode": "USER_SCOPED_ADMIN",
            "repository_creation_endpoint": "https://api.github.com/user/repos",
            "owner_authority_preserved": True,
            "provider_apply_performed": False,
            "external_commercial_gates_advanced": False,
        }
        self.decision = self_hash(decision_body, "decision_sha256")

    def build(self):
        return MODULE.build_intake(
            identity_receipt=self.identity,
            authority_receipt=self.authority,
            decision=self.decision,
            now=self.now,
        )

    def test_valid_intake_is_hash_bound_and_non_executing(self):
        result = self.build()
        self.assertEqual(
            "PROVIDER_ATTESTED_AUTHORIZATION_INTAKE_VERIFIED_"
            "LIVE_REPROBE_AND_OWNER_RESERVED_APPLY_REQUIRED",
            result["status"],
        )
        self.assertFalse(result["provider_request_performed"])
        self.assertFalse(result["provider_apply_performed"])
        self.assertFalse(result["authorization_consumption_state_created"])
        claimed = result["intake_sha256"]
        body = dict(result)
        body.pop("intake_sha256")
        self.assertEqual(claimed, MODULE.canonical_sha256(body))

    def test_mock_identity_receipt_fails_closed(self):
        self.identity["capture_mode"] = "MOCK_CONFORMANCE"
        self.identity["receipt_sha256"] = MODULE.canonical_sha256(
            {k: v for k, v in self.identity.items() if k != "receipt_sha256"}
        )
        with self.assertRaises(MODULE.ProviderAttestedAuthorizationError):
            self.build()

    def test_tampered_identity_receipt_fails_closed(self):
        self.identity["comment_id"] = 7
        with self.assertRaises(MODULE.ProviderAttestedAuthorizationError):
            self.build()

    def test_decision_binding_mismatch_fails_closed(self):
        self.decision["provider_identity_receipt_sha256"] = "f" * 64
        self.decision["decision_sha256"] = MODULE.canonical_sha256(
            {k: v for k, v in self.decision.items() if k != "decision_sha256"}
        )
        with self.assertRaises(MODULE.ProviderAttestedAuthorizationError):
            self.build()

    def test_expired_decision_fails_closed(self):
        with self.assertRaises(MODULE.ProviderAttestedAuthorizationError):
            MODULE.build_intake(
                identity_receipt=self.identity,
                authority_receipt=self.authority,
                decision=self.decision,
                now=self.now + timedelta(minutes=10),
                max_age_seconds=1000,
            )

    def test_contract_checkpoint_projection_and_export_truth(self):
        contract = json.loads(CONTRACT.read_text())
        checkpoint = json.loads(CHECKPOINT.read_text())
        projection = json.loads(PROJECTION.read_text())
        policy = json.loads(POLICY.read_text())

        self.assertEqual("PREPARED_NOT_EXECUTED_OWNER_RESERVED", contract["status"])
        self.assertFalse(contract["controls"]["provider_apply_performed"])
        self.assertFalse(contract["controls"]["external_commercial_gate_advanced"])
        self.assertEqual(
            "PROVIDER_ATTESTED_AUTHORIZATION_INTAKE_IMPLEMENTED_"
            "PROVIDER_PROOF_REQUIRED_OWNER_EXECUTION_AND_FRESH_AUTHORITY_REQUIRED",
            checkpoint["status"],
        )
        self.assertFalse(checkpoint["commercial_truth"]["full_commercial_maturity"])
        self.assertEqual(0, checkpoint["commercial_truth"]["verified_live_revenue_events"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        required = set(policy["ops"]["required_files"])
        self.assertIn("provider_attested_authorization.py", required)
        self.assertIn(
            "governance/PROVIDER_ATTESTED_AUTHORIZATION_CONTRACT.json", required
        )


if __name__ == "__main__":
    unittest.main()
