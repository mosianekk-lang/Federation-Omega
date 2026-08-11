from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from phoenix.provider_cutover_authorized_executor import (
    AuthorizedCutoverError,
    execute_authorized_cutover,
    prepare_execution,
)

NOW = datetime(2026, 8, 4, 21, 0, tzinfo=timezone.utc)
SOURCE_SHA = "b" * 40
EXECUTION_ID = "execution-20260804-0001"


class AuthorizedCutoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core = self.root / "core.tar.gz"
        self.ops = self.root / "ops.tar.gz"
        self.core.write_bytes(b"core")
        self.ops.write_bytes(b"ops")
        self.state = self.root / "state"
        self.receipt = self.root / "provider-receipt.json"
        self.decision = {
            "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-1",
            "status": "AUTHORIZED_APPLY",
            "authorization_id": "AO-PHX-AUTH-20260804-009",
            "authorization_sha256": "a" * 64,
            "source_sha": SOURCE_SHA,
            "core_archive_sha256": hashlib.sha256(b"core").hexdigest(),
            "ops_archive_sha256": hashlib.sha256(b"ops").hexdigest(),
            "authority_mode": "INSTALLATION_TEMPLATE",
            "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
            "owner_authority_preserved": True,
            "credential_value_recorded": False,
            "external_commercial_gates_advanced": False,
        }
        controller = (
            Path(__file__).resolve().parents[1]
            / "phoenix"
            / "provider_cutover_v3_1.py"
        )
        self.assertTrue(controller.is_file())

    def tearDown(self):
        self.temp.cleanup()

    def write_receipt(self, *, ops_verified: bool = True) -> None:
        receipt = {
            "schema": "FEDOMEGA-PHOENIX-PROVIDER-CUTOVER-3",
            "status": "VERIFIED",
            "owner": "mosianekk-lang",
            "core": "Federation-Omega-Core",
            "ops": "Federation-Omega-Ops",
            "core_archive_sha256": self.decision["core_archive_sha256"],
            "ops_archive_sha256": self.decision["ops_archive_sha256"],
            "core_readback": {"verified": True},
            "ops_readback": {"verified": ops_verified},
            "legacy_actions_disabled": True,
            "credential_value_recorded": False,
        }
        canonical = json.dumps(
            receipt, sort_keys=True, separators=(",", ":")
        ).encode()
        receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
        self.receipt.write_text(json.dumps(receipt), encoding="utf-8")

    def execute(self, **overrides):
        arguments = {
            "state_dir": self.state,
            "execution_id": EXECUTION_ID,
            "source_sha": SOURCE_SHA,
            "core_archive": self.core,
            "ops_archive": self.ops,
            "provider_receipt_path": self.receipt,
            "now": NOW,
            "provider_authority_available": True,
            "runner": lambda command: 1,
        }
        arguments.update(overrides)
        return execute_authorized_cutover(self.decision, **arguments)

    def test_preflight_binds_exact_source_and_archives(self):
        result = prepare_execution(
            self.decision,
            source_sha=SOURCE_SHA,
            core_archive=self.core,
            ops_archive=self.ops,
            now=NOW,
        )
        self.assertEqual(
            "READY_FOR_OWNER_AUTHORISED_PROVIDER_APPLY", result["status"]
        )
        self.assertEqual(
            self.decision["core_archive_sha256"],
            result["core_archive_sha256"],
        )

    def test_missing_provider_authority_does_not_consume_authorization(self):
        result = self.execute(provider_authority_available=False)
        self.assertEqual(
            "PROVIDER_BLOCKED_NO_FRESH_GITHUB_AUTHORITY", result["status"]
        )
        self.assertFalse(self.state.exists())
        self.assertFalse(result["provider_apply_invoked"])

    def test_verified_receipt_completes_one_time_apply(self):
        commands: list[list[str]] = []

        def run(command: list[str]) -> int:
            commands.append(command)
            self.write_receipt()
            return 0

        result = self.execute(runner=run)
        self.assertEqual("VERIFIED", result["status"])
        self.assertTrue(result["authorization_use"]["provider_apply_performed"])
        self.assertEqual(1, len(commands))
        self.assertNotIn("GH_ADMIN_TOKEN", " ".join(commands[0]))

    def test_nonzero_exit_with_valid_receipt_is_conclusive(self):
        def run(_: list[str]) -> int:
            self.write_receipt()
            return 7

        result = self.execute(runner=run)
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual(7, result["provider_exit_code"])

    def test_failed_runner_is_not_retried(self):
        result = self.execute(runner=lambda _: 1)
        self.assertEqual(
            "PROVIDER_OUTCOME_RECONCILIATION_REQUIRED", result["status"]
        )
        called: list[list[str]] = []
        again = self.execute(
            now=NOW + timedelta(seconds=1),
            runner=lambda command: called.append(command) or 0,
        )
        self.assertEqual(
            "PROVIDER_OUTCOME_RECONCILIATION_REQUIRED", again["status"]
        )
        self.assertFalse(called)
        self.assertFalse(again["automatic_retry_performed"])

    def test_existing_receipt_reconciles_after_authorization_expiry(self):
        self.execute(runner=lambda _: 1)
        self.write_receipt()
        called: list[list[str]] = []
        result = self.execute(
            now=NOW + timedelta(hours=1),
            runner=lambda command: called.append(command) or 99,
        )
        self.assertEqual(
            "VERIFIED_FROM_EXISTING_PROVIDER_RECEIPT", result["status"]
        )
        self.assertFalse(called)

    def test_invalid_existing_receipt_does_not_retry(self):
        self.execute(runner=lambda _: 1)
        self.write_receipt(ops_verified=False)
        called: list[list[str]] = []
        result = self.execute(
            now=NOW + timedelta(hours=1),
            runner=lambda command: called.append(command) or 0,
        )
        self.assertEqual(
            "PROVIDER_OUTCOME_RECONCILIATION_REQUIRED", result["status"]
        )
        self.assertIn("semantic verification", result["provider_receipt_error"])
        self.assertFalse(called)

    def test_exact_verified_retry_is_idempotent(self):
        def run(_: list[str]) -> int:
            self.write_receipt()
            return 0

        first = self.execute(runner=run)
        called: list[list[str]] = []
        second = self.execute(
            now=NOW + timedelta(hours=1),
            runner=lambda command: called.append(command) or 0,
        )
        self.assertEqual("VERIFIED", first["status"])
        self.assertEqual("VERIFIED_IDEMPOTENT", second["status"])
        self.assertFalse(called)

    def test_cross_execution_replay_is_rejected(self):
        self.execute(runner=lambda _: 1)
        with self.assertRaisesRegex(
            AuthorizedCutoverError, "conflicts with this execution"
        ):
            self.execute(
                execution_id="execution-20260804-0002",
                now=NOW + timedelta(seconds=1),
            )

    def test_mismatch_is_rejected_before_state_creation(self):
        with self.assertRaises(AuthorizedCutoverError):
            prepare_execution(
                self.decision,
                source_sha="c" * 40,
                core_archive=self.core,
                ops_archive=self.ops,
                now=NOW,
            )
        self.assertFalse(self.state.exists())

    def test_invalid_authority_mode_is_rejected(self):
        self.decision["authority_mode"] = "UNSCOPED"
        with self.assertRaisesRegex(AuthorizedCutoverError, "authority_mode"):
            prepare_execution(
                self.decision,
                source_sha=SOURCE_SHA,
                core_archive=self.core,
                ops_archive=self.ops,
                now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
