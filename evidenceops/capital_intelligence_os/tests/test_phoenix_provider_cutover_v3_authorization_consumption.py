from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from phoenix.provider_cutover_authorization_use import (
    AuthorizationUseError,
    reserve_authorization,
    transition_authorization,
)


NOW = datetime(2026, 8, 4, 20, 0, tzinfo=timezone.utc)
AUTH_SHA = "a" * 64
SOURCE_SHA = "b" * 40
CORE_SHA = "c" * 64
OPS_SHA = "d" * 64
RECEIPT_SHA = "e" * 64


def decision() -> dict:
    return {
        "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-1",
        "status": "AUTHORIZED_APPLY",
        "authorization_id": "AO-PHX-AUTH-20260804-002",
        "authorization_sha256": AUTH_SHA,
        "source_sha": SOURCE_SHA,
        "core_archive_sha256": CORE_SHA,
        "ops_archive_sha256": OPS_SHA,
        "authority_mode": "INSTALLATION_TEMPLATE",
        "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
        "owner_authority_preserved": True,
        "credential_value_recorded": False,
        "external_commercial_gates_advanced": False,
    }


class AuthorizationConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp.name) / "authorization-use"

    def tearDown(self):
        self.temp.cleanup()

    def reserve(self, payload: dict | None = None, execution_id: str = "execution-20260804-0001"):
        return reserve_authorization(
            payload or decision(),
            state_dir=self.state_dir,
            execution_id=execution_id,
            now=NOW,
        )

    def test_exact_authorization_is_reserved_once(self):
        record = self.reserve()
        self.assertEqual(record["reservation_result"], "RESERVED_NEW")
        self.assertEqual(record["state"], "RESERVED")
        self.assertFalse(record["provider_apply_performed"])
        self.assertFalse(record["credential_value_recorded"])
        self.assertFalse(record["external_commercial_gates_advanced"])

    def test_exact_retry_is_idempotent(self):
        first = self.reserve()
        second = self.reserve()
        self.assertEqual(second["reservation_result"], "IDEMPOTENT_EXISTING")
        self.assertEqual(first["record_sha256"], second["record_sha256"])

    def test_same_authorization_cannot_be_replayed_by_another_execution(self):
        self.reserve()
        with self.assertRaisesRegex(AuthorizationUseError, "already been consumed"):
            self.reserve(execution_id="execution-20260804-0002")

    def test_expired_decision_is_rejected_before_reservation(self):
        payload = decision()
        payload["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(AuthorizationUseError, "expired"):
            self.reserve(payload)
        self.assertFalse(self.state_dir.exists())

    def test_secret_bearing_decision_is_rejected(self):
        payload = decision()
        payload["token"] = "github_pat_example_value_12345678901234567890"
        with self.assertRaisesRegex(AuthorizationUseError, "secret-bearing field"):
            self.reserve(payload)

    def test_apply_must_start_before_terminal_transition(self):
        self.reserve()
        with self.assertRaisesRegex(AuthorizationUseError, "cannot finish apply"):
            transition_authorization(
                state_dir=self.state_dir,
                authorization_sha256=AUTH_SHA,
                execution_id="execution-20260804-0001",
                target_state="VERIFIED",
                provider_receipt_sha256=RECEIPT_SHA,
                now=NOW + timedelta(seconds=1),
            )

    def test_verified_transition_requires_hash_bound_provider_receipt(self):
        self.reserve()
        started = transition_authorization(
            state_dir=self.state_dir,
            authorization_sha256=AUTH_SHA,
            execution_id="execution-20260804-0001",
            target_state="APPLY_STARTED",
            now=NOW + timedelta(seconds=1),
        )
        self.assertEqual(started["state"], "APPLY_STARTED")
        with self.assertRaisesRegex(AuthorizationUseError, "requires provider_receipt_sha256"):
            transition_authorization(
                state_dir=self.state_dir,
                authorization_sha256=AUTH_SHA,
                execution_id="execution-20260804-0001",
                target_state="VERIFIED",
                now=NOW + timedelta(seconds=2),
            )
        verified = transition_authorization(
            state_dir=self.state_dir,
            authorization_sha256=AUTH_SHA,
            execution_id="execution-20260804-0001",
            target_state="VERIFIED",
            provider_receipt_sha256=RECEIPT_SHA,
            now=NOW + timedelta(seconds=3),
        )
        self.assertTrue(verified["provider_apply_performed"])
        self.assertEqual(verified["provider_receipt_sha256"], RECEIPT_SHA)

    def test_terminal_record_is_immutable_and_exact_retry_is_idempotent(self):
        self.reserve()
        transition_authorization(
            state_dir=self.state_dir,
            authorization_sha256=AUTH_SHA,
            execution_id="execution-20260804-0001",
            target_state="APPLY_STARTED",
            now=NOW + timedelta(seconds=1),
        )
        first = transition_authorization(
            state_dir=self.state_dir,
            authorization_sha256=AUTH_SHA,
            execution_id="execution-20260804-0001",
            target_state="VERIFIED",
            provider_receipt_sha256=RECEIPT_SHA,
            now=NOW + timedelta(seconds=2),
        )
        second = transition_authorization(
            state_dir=self.state_dir,
            authorization_sha256=AUTH_SHA,
            execution_id="execution-20260804-0001",
            target_state="VERIFIED",
            provider_receipt_sha256=RECEIPT_SHA,
            now=NOW + timedelta(seconds=3),
        )
        self.assertEqual(second["transition_result"], "IDEMPOTENT_EXISTING")
        self.assertEqual(first["record_sha256"], second["record_sha256"])
        with self.assertRaisesRegex(AuthorizationUseError, "terminal"):
            transition_authorization(
                state_dir=self.state_dir,
                authorization_sha256=AUTH_SHA,
                execution_id="execution-20260804-0001",
                target_state="ABORTED",
                now=NOW + timedelta(seconds=4),
            )

    def test_tampered_record_is_rejected(self):
        self.reserve()
        path = self.state_dir / f"{AUTH_SHA}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["execution_id"] = "execution-20260804-attacker"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(AuthorizationUseError, "integrity verification"):
            self.reserve()


if __name__ == "__main__":
    unittest.main()
