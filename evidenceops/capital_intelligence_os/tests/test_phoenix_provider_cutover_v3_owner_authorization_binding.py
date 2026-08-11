from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from phoenix.provider_cutover_authorization import (
    AuthorizationError,
    CONFIRMATION,
    canonical_sha256,
)
from phoenix.provider_cutover_authorization_v2 import validate_authorization_v2

SOURCE_SHA = "a" * 40
CORE_SHA = "b" * 64
OPS_SHA = "c" * 64
NOW = datetime(2026, 8, 5, 2, 0, tzinfo=timezone.utc)
ENDPOINT = "/repos/mosianekk-lang/Federation-Omega/generate"


def authority_receipt(mode: str = "INSTALLATION_TEMPLATE") -> dict:
    body = {
        "schema": "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1",
        "status": "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY",
        "observed_at": NOW.isoformat(),
        "owner": "mosianekk-lang",
        "legacy": "Federation-Omega",
        "core": "Federation-Omega-Core",
        "ops": "Federation-Omega-Ops",
        "legacy_main_sha": SOURCE_SHA,
        "core_target_exists": False,
        "ops_target_exists": False,
        "route": {
            "authority_mode": mode,
            "repository_creation_endpoint": (
                ENDPOINT if mode == "INSTALLATION_TEMPLATE" else "/user/repos"
            ),
        },
        "checks": {"owner_identity": True, "legacy_admin": True},
        "blockers": [],
        "owner_authorization_still_required": True,
        "provider_apply_performed": False,
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def payload(receipt: dict | None = None) -> dict:
    receipt = receipt or authority_receipt()
    return {
        "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-2",
        "authorization_id": "AO-PHX-AUTH-V2-20260805-001",
        "nonce": "owner-authority-binding-nonce-0001",
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
        "authority_mode": receipt["route"]["authority_mode"],
        "provider_authority_receipt_sha256": receipt["receipt_sha256"],
        "repository_creation_endpoint": receipt["route"][
            "repository_creation_endpoint"
        ],
        "credential_source_env": "GH_ADMIN_TOKEN",
        "issued_at": (NOW - timedelta(seconds=30)).isoformat(),
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


class OwnerAuthorizationBindingTests(unittest.TestCase):
    def validate(self, value: dict, receipt: dict):
        return validate_authorization_v2(
            value,
            authority_receipt=receipt,
            now=NOW,
            source_sha=SOURCE_SHA,
            core_archive_sha256=CORE_SHA,
            ops_archive_sha256=OPS_SHA,
        )

    def test_exact_owner_and_provider_authority_binding_is_admitted(self):
        receipt = authority_receipt()
        decision = self.validate(payload(receipt), receipt)
        self.assertEqual(
            "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2",
            decision["schema"],
        )
        self.assertEqual(receipt["receipt_sha256"], decision["provider_authority_receipt_sha256"])
        self.assertEqual(ENDPOINT, decision["repository_creation_endpoint"])
        self.assertTrue(decision["provider_authority_binding_required"])
        self.assertFalse(decision["credential_value_recorded"])
        self.assertFalse(decision["external_commercial_gates_advanced"])

    def test_authority_receipt_digest_drift_is_rejected(self):
        receipt = authority_receipt()
        value = payload(receipt)
        value["provider_authority_receipt_sha256"] = "d" * 64
        with self.assertRaisesRegex(AuthorizationError, "exact receipt"):
            self.validate(value, receipt)

    def test_repository_creation_endpoint_drift_is_rejected(self):
        receipt = authority_receipt()
        value = payload(receipt)
        value["repository_creation_endpoint"] = "/user/repos"
        with self.assertRaisesRegex(AuthorizationError, "exact provider route"):
            self.validate(value, receipt)

    def test_authority_mode_drift_is_rejected(self):
        receipt = authority_receipt()
        value = payload(receipt)
        value["authority_mode"] = "USER_SCOPED"
        with self.assertRaisesRegex(AuthorizationError, "authority_mode"):
            self.validate(value, receipt)

    def test_tampered_authority_receipt_is_rejected(self):
        receipt = authority_receipt()
        value = payload(receipt)
        receipt["owner"] = "other"
        with self.assertRaisesRegex(AuthorizationError, "hash verification"):
            self.validate(value, receipt)

    def test_unsafe_provider_receipt_is_rejected(self):
        receipt = authority_receipt()
        receipt["provider_mutation_performed"] = True
        receipt["receipt_sha256"] = canonical_sha256(
            {key: item for key, item in receipt.items() if key != "receipt_sha256"}
        )
        value = payload(receipt)
        with self.assertRaisesRegex(AuthorizationError, "unsafe provider_mutation_performed"):
            self.validate(value, receipt)

    def test_external_authority_remains_rejected(self):
        receipt = authority_receipt()
        value = copy.deepcopy(payload(receipt))
        value["actions"]["payment_operation"] = True
        with self.assertRaisesRegex(AuthorizationError, "payment_operation"):
            self.validate(value, receipt)


if __name__ == "__main__":
    unittest.main()
