from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "phoenix"
    / "ops-template"
    / "provider_cutover_owner_authority_bound.py"
)
SPEC = importlib.util.spec_from_file_location("owner_authority_bound_test", PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)
NOW = datetime(2026, 8, 5, 2, 15, tzinfo=timezone.utc)
SOURCE = "a" * 40
ENDPOINT = "/repos/mosianekk-lang/Federation-Omega/generate"


def authority_receipt() -> dict:
    body = {
        "schema": "FEDOMEGA-PHOENIX-PROVIDER-AUTHORITY-PROBE-1",
        "status": "AUTHORITY_READY_FOR_FRESH_OWNER_AUTHORISED_APPLY",
        "observed_at": NOW.isoformat(),
        "owner": "mosianekk-lang",
        "legacy": "Federation-Omega",
        "core": "Federation-Omega-Core",
        "ops": "Federation-Omega-Ops",
        "legacy_main_sha": SOURCE,
        "core_target_exists": False,
        "ops_target_exists": False,
        "route": {
            "authority_mode": "INSTALLATION_TEMPLATE",
            "repository_creation_endpoint": ENDPOINT,
        },
        "checks": {"owner_identity": True, "legacy_admin": True},
        "blockers": [],
        "owner_authorization_still_required": True,
        "provider_apply_performed": False,
        "provider_mutation_performed": False,
        "credential_value_recorded": False,
    }
    body["receipt_sha256"] = MOD._load_authority_bound_module().canonical_sha256(body)
    return body


def decision(receipt: dict) -> dict:
    return {
        "schema": "FEDOMEGA-PHOENIX-CUTOVER-AUTHORIZATION-DECISION-2",
        "status": "AUTHORIZED_APPLY",
        "authorization_id": "AO-PHX-AUTH-V2-20260805-001",
        "authorization_sha256": "d" * 64,
        "source_sha": SOURCE,
        "core_archive_sha256": "b" * 64,
        "ops_archive_sha256": "c" * 64,
        "authority_mode": "INSTALLATION_TEMPLATE",
        "expires_at": "2026-08-05T02:25:00+00:00",
        "provider_authority_receipt_sha256": receipt["receipt_sha256"],
        "repository_creation_endpoint": ENDPOINT,
        "provider_authority_binding_required": True,
        "owner_authority_preserved": True,
        "credential_value_recorded": False,
        "external_commercial_gates_advanced": False,
    }


class OwnerAuthorityBoundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.state = root / "state"
        self.core = root / "core.tar.gz"
        self.ops = root / "ops.tar.gz"
        self.provider = root / "provider.json"
        self.core.write_bytes(b"core")
        self.ops.write_bytes(b"ops")

    def tearDown(self):
        self.temp.cleanup()

    def install_fake_base(self):
        fake = types.SimpleNamespace()
        fake.canonical_sha256 = lambda payload: __import__("hashlib").sha256(
            __import__("json").dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        fake.execute_authority_bound_cutover = lambda *args, **kwargs: {
            "status": "VERIFIED",
            "provider_apply_invoked": True,
            "provider_authority": {"status": "AUTHORITY_CONTINUITY_VERIFIED"},
        }
        MOD._load_authority_bound_module = lambda: fake

    def test_exact_binding_delegates_to_existing_guard_chain(self):
        self.install_fake_base()
        receipt = authority_receipt()
        result = MOD.execute_owner_authority_bound_cutover(
            {"source_sha": SOURCE},
            decision(receipt),
            receipt,
            state_dir=self.state,
            execution_id="exec-1",
            core_archive=self.core,
            ops_archive=self.ops,
            provider_receipt_path=self.provider,
            provider_authority_available=True,
            source_head_reader=lambda owner, legacy: SOURCE,
            authority_reprobe=lambda: receipt,
            now=NOW,
        )
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual(
            "provider_cutover_owner_authority_bound.py",
            result["canonical_apply_entrypoint"],
        )
        self.assertEqual(
            "OWNER_AUTHORITY_BINDING_VERIFIED",
            result["owner_authority_binding"]["status"],
        )

    def test_receipt_digest_drift_blocks_before_delegation(self):
        self.install_fake_base()
        receipt = authority_receipt()
        value = decision(receipt)
        value["provider_authority_receipt_sha256"] = "e" * 64
        result = MOD.execute_owner_authority_bound_cutover(
            {"source_sha": SOURCE},
            value,
            receipt,
            state_dir=self.state,
            execution_id="exec-1",
            core_archive=self.core,
            ops_archive=self.ops,
            provider_receipt_path=self.provider,
            provider_authority_available=True,
            now=NOW,
        )
        self.assertEqual("OWNER_AUTHORITY_BINDING_INVALIDATED", result["status"])
        self.assertFalse(result["provider_apply_invoked"])
        self.assertFalse(self.state.exists())

    def test_endpoint_drift_blocks_before_delegation(self):
        self.install_fake_base()
        receipt = authority_receipt()
        value = decision(receipt)
        value["repository_creation_endpoint"] = "/user/repos"
        result = MOD.execute_owner_authority_bound_cutover(
            {"source_sha": SOURCE},
            value,
            receipt,
            state_dir=self.state,
            execution_id="exec-1",
            core_archive=self.core,
            ops_archive=self.ops,
            provider_receipt_path=self.provider,
            provider_authority_available=True,
            now=NOW,
        )
        self.assertEqual("OWNER_AUTHORITY_BINDING_INVALIDATED", result["status"])
        self.assertIn("repository_creation_endpoint", result["binding_error"])
        self.assertFalse(self.state.exists())

    def test_tampered_receipt_blocks_before_delegation(self):
        self.install_fake_base()
        receipt = authority_receipt()
        value = decision(receipt)
        receipt["owner"] = "other"
        result = MOD.execute_owner_authority_bound_cutover(
            {"source_sha": SOURCE},
            value,
            receipt,
            state_dir=self.state,
            execution_id="exec-1",
            core_archive=self.core,
            ops_archive=self.ops,
            provider_receipt_path=self.provider,
            provider_authority_available=True,
            now=NOW,
        )
        self.assertEqual("OWNER_AUTHORITY_BINDING_INVALIDATED", result["status"])
        self.assertIn("hash verification", result["binding_error"])
        self.assertFalse(self.state.exists())

    def test_owner_decision_cannot_advance_external_commercial_gates(self):
        self.install_fake_base()
        receipt = authority_receipt()
        value = decision(receipt)
        value["external_commercial_gates_advanced"] = True
        result = MOD.execute_owner_authority_bound_cutover(
            {"source_sha": SOURCE},
            value,
            receipt,
            state_dir=self.state,
            execution_id="exec-1",
            core_archive=self.core,
            ops_archive=self.ops,
            provider_receipt_path=self.provider,
            provider_authority_available=True,
            now=NOW,
        )
        self.assertEqual("OWNER_AUTHORITY_BINDING_INVALIDATED", result["status"])
        self.assertIn("commercial gates", result["binding_error"])


if __name__ == "__main__":
    unittest.main()
