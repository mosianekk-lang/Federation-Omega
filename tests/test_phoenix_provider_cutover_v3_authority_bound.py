from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
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
):
    body = {
        "schema": "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1",
        "status": status,
        "observed_at": NOW.isoformat(),
        "owner": "mosianekk-lang",
        "legacy": "Federation-Omega",
        "core": "Federation-Omega-Core",
        "ops": "Federation-Omega-Ops",
        "legacy_main_sha": SOURCE,
        "core_target_exists": False,
        "ops_target_exists": False,
        "route": {"authority_mode": mode},
        "checks": {},
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

    def execute(self, value, available=True):
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
            now=NOW,
        )

    def test_ready_receipt_delegates(self):
        result = self.execute(receipt())
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual(
            "provider_cutover_authority_bound.py",
            result["canonical_apply_entrypoint"],
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


if __name__ == "__main__":
    unittest.main()
