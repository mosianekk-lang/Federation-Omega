from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "phoenix" / "ops-template" / "provider_cutover_authority_bound.py"
SPEC = importlib.util.spec_from_file_location("authority_bound_test", PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)
NOW = datetime(2026, 8, 5, 0, 0, tzinfo=timezone.utc)
SOURCE = "a" * 40


def candidate():
    return {"source_sha": SOURCE}


def decision(mode="INSTALLATION_TEMPLATE"):
    return {"authority_mode": mode}


def receipt(
    status="AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY",
    mode="INSTALLATION_TEMPLATE",
    observed_at=NOW,
    source=SOURCE,
    core_exists=False,
    ops_exists=False,
):
    body = {
        "schema": "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1",
        "status": status,
        "observed_at": observed_at.isoformat(),
        "owner": "mosianekk-lang",
        "legacy": "Federation-Omega",
        "core": "Federation-Omega-Core",
        "ops": "Federation-Omega-Ops",
        "legacy_main_sha": source,
        "core_target_exists": core_exists,
        "ops_target_exists": ops_exists,
        "route": {
            "authority_mode": mode,
            "repository_creation_endpoint": (
                "/repos/mosianekk-lang/Federation-Omega/generate"
                if mode == "INSTALLATION_TEMPLATE"
                else "/user/repos"
            ),
        },
        "checks": {
            "owner_identity": True,
            "legacy_admin": True,
            "legacy_main_readable": True,
        },
        "blockers": [],
        "owner_authorization_still_required": True,
        "provider_apply_performed": False,
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
    }
    body["receipt_sha256"] = MOD.canonical_sha256(body)
    return body


class AuthorityBoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.state = root / "state"
        self.core = root / "core.tar.gz"
        self.ops = root / "ops.tar.gz"
        self.provider = root / "provider.json"
        self.core.write_bytes(b"core")
        self.ops.write_bytes(b"ops")
        fake = types.SimpleNamespace()
        fake.execute_candidate_cutover = lambda *args, **kwargs: {
            "status": "VERIFIED",
            "provider_apply_invoked": True,
        }
        MOD._load_candidate_module = lambda: fake

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, value, *, available=True, live=None, reprobe_error=None):
        def reprobe():
            if reprobe_error is not None:
                raise MOD.AuthorityBoundError(reprobe_error)
            return live if live is not None else receipt()

        return MOD.execute_authority_bound_cutover(
            candidate(),
            decision(),
            value,
            state_dir=self.state,
            execution_id="exec-1",
            core_archive=self.core,
            ops_archive=self.ops,
            provider_receipt_path=self.provider,
            provider_authority_available=available,
            source_head_reader=lambda owner, legacy: SOURCE,
            authority_reprobe=reprobe,
            now=NOW,
        )

    def test_ready_receipt_and_live_reprobe_delegate(self):
        result = self.execute(receipt())
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual(
            "provider_cutover_authority_bound.py",
            result["canonical_apply_entrypoint"],
        )
        self.assertEqual(
            "AUTHORITY_CONTINUITY_VERIFIED",
            result["provider_authority"]["status"],
        )
        self.assertTrue(
            result["provider_authority"]["just_in_time_reprobe_get_only"]
        )

    def test_no_private_credential_blocks_before_state(self):
        result = self.execute(receipt(), available=False)
        self.assertEqual("AUTHORITY_BLOCKED_NO_PRIVATE_CREDENTIAL", result["status"])
        self.assertFalse(self.state.exists())

    def test_selected_repository_receipt_blocks(self):
        result = self.execute(
            receipt(status="AUTHORITY_BLOCKED_EXACT_REMEDIATION_REQUIRED")
        )
        self.assertEqual("AUTHORITY_INVALIDATED", result["status"])
        self.assertFalse(self.state.exists())

    def test_mode_mismatch_blocks(self):
        result = self.execute(receipt(mode="USER_SCOPED"))
        self.assertEqual("AUTHORITY_INVALIDATED", result["status"])
        self.assertIn("mode does not match", result["authority_error"])

    def test_tamper_blocks(self):
        value = receipt()
        value["owner"] = "other"
        result = self.execute(value)
        self.assertEqual("AUTHORITY_INVALIDATED", result["status"])
        self.assertIn("embedded SHA-256", result["authority_error"])

    def test_stale_initial_receipt_blocks_before_reprobe(self):
        value = receipt(observed_at=NOW - timedelta(seconds=301))
        result = self.execute(value)
        self.assertEqual("AUTHORITY_INVALIDATED", result["status"])
        self.assertIn("stale", result["authority_error"])
        self.assertFalse(self.state.exists())

    def test_implausible_future_receipt_blocks(self):
        value = receipt(observed_at=NOW + timedelta(seconds=31))
        result = self.execute(value)
        self.assertEqual("AUTHORITY_INVALIDATED", result["status"])
        self.assertIn("future", result["authority_error"])

    def test_live_reprobe_failure_blocks_before_state(self):
        result = self.execute(receipt(), reprobe_error="provider readback failed")
        self.assertEqual("AUTHORITY_REPROBE_FAILED", result["status"])
        self.assertFalse(self.state.exists())

    def test_live_reprobe_blocked_authority_fails_closed(self):
        live = receipt(status="AUTHORITY_BLOCKED_EXACT_REMEDIATION_REQUIRED")
        result = self.execute(receipt(), live=live)
        self.assertEqual("AUTHORITY_REPROBE_FAILED", result["status"])
        self.assertIn("not ready", result["authority_error"])
        self.assertFalse(self.state.exists())

    def test_target_topology_drift_invalidates_continuity(self):
        result = self.execute(receipt(), live=receipt(core_exists=True))
        self.assertEqual("AUTHORITY_CONTINUITY_INVALIDATED", result["status"])
        self.assertIn("core_target_exists", result["authority_error"])
        self.assertFalse(self.state.exists())

    def test_failed_semantic_check_invalidates_hash_valid_receipt(self):
        value = receipt()
        value["checks"]["legacy_admin"] = False
        value["receipt_sha256"] = MOD.canonical_sha256(
            {key: item for key, item in value.items() if key != "receipt_sha256"}
        )
        result = self.execute(value)
        self.assertEqual("AUTHORITY_INVALIDATED", result["status"])
        self.assertIn("failed or invalid checks", result["authority_error"])


if __name__ == "__main__":
    unittest.main()
