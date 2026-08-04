from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from phoenix.provider_cutover_authorization import (
    AuthorizationError,
    CONFIRMATION,
    validate_authorization,
)


SOURCE_SHA = "a" * 40
CORE_SHA = "b" * 64
OPS_SHA = "c" * 64
NOW = datetime(2026, 8, 4, 19, 10, tzinfo=timezone.utc)


def valid_payload() -> dict:
    return {
        "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-1",
        "authorization_id": "AO-PHX-AUTH-20260804-001",
        "nonce": "nonce-20260804-owner-0001",
        "owner_display_name": "Kim Kagiso Mosiane",
        "github_owner": "mosianekk-lang",
        "source_repository": "Federation-Omega",
        "core_repository": "Federation-Omega-Core",
        "ops_repository": "Federation-Omega-Ops",
        "source_sha": SOURCE_SHA,
        "core_archive_sha256": CORE_SHA,
        "ops_archive_sha256": OPS_SHA,
        "core_private": False,
        "ops_private": True,
        "authority_mode": "INSTALLATION_TEMPLATE",
        "credential_source_env": "GH_ADMIN_TOKEN",
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
        "owner_confirmation": CONFIRMATION,
        "actions": {
            "provider_apply": True,
            "create_core": True,
            "create_ops": True,
            "replace_existing_main": True,
            "archive_legacy": False,
            "cloud_run_operation": False,
            "payment_operation": False,
            "external_communication": False,
            "financial_commitment": False,
            "contract_action": False,
            "revenue_recognition": False,
        },
    }


class PhoenixAuthorizationTests(unittest.TestCase):
    def validate(self, payload: dict):
        return validate_authorization(
            payload,
            now=NOW,
            source_sha=SOURCE_SHA,
            core_archive_sha256=CORE_SHA,
            ops_archive_sha256=OPS_SHA,
        )

    def test_exact_owner_authorization_is_admitted(self):
        decision = self.validate(valid_payload())
        self.assertEqual(decision["status"], "AUTHORIZED_APPLY")
        self.assertTrue(decision["owner_authority_preserved"])
        self.assertFalse(decision["credential_value_recorded"])
        self.assertFalse(decision["external_commercial_gates_advanced"])

    def test_expired_authorization_is_rejected(self):
        payload = valid_payload()
        payload["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(AuthorizationError, "expired"):
            self.validate(payload)

    def test_archive_drift_is_rejected(self):
        payload = valid_payload()
        payload["core_archive_sha256"] = "d" * 64
        with self.assertRaisesRegex(AuthorizationError, "core_archive_sha256"):
            self.validate(payload)

    def test_source_drift_is_rejected(self):
        payload = valid_payload()
        payload["source_sha"] = "e" * 40
        with self.assertRaisesRegex(AuthorizationError, "source_sha"):
            self.validate(payload)

    def test_secret_bearing_field_is_rejected(self):
        payload = valid_payload()
        payload["token"] = "github_pat_example_not_allowed_1234567890"
        with self.assertRaisesRegex(AuthorizationError, "secret-bearing field"):
            self.validate(payload)

    def test_external_or_financial_authority_is_rejected(self):
        for action in (
            "cloud_run_operation",
            "payment_operation",
            "external_communication",
            "financial_commitment",
            "contract_action",
            "revenue_recognition",
        ):
            payload = copy.deepcopy(valid_payload())
            payload["actions"][action] = True
            with self.subTest(action=action):
                with self.assertRaisesRegex(AuthorizationError, action):
                    self.validate(payload)

    def test_ops_repository_must_remain_private(self):
        payload = valid_payload()
        payload["ops_private"] = False
        with self.assertRaisesRegex(AuthorizationError, "ops_private"):
            self.validate(payload)

    def test_authorization_lifetime_is_bounded(self):
        payload = valid_payload()
        payload["expires_at"] = (NOW + timedelta(minutes=31)).isoformat()
        with self.assertRaisesRegex(AuthorizationError, "1-1800 seconds"):
            self.validate(payload)

    def test_confirmation_phrase_is_exact(self):
        payload = valid_payload()
        payload["owner_confirmation"] = "authorise cutover"
        with self.assertRaisesRegex(AuthorizationError, "owner_confirmation"):
            self.validate(payload)


if __name__ == "__main__":
    unittest.main()
