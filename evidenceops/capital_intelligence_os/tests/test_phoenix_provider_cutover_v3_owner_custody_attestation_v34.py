from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "phoenix" / "ops-template" / "owner_sealed_packet.py"
PACKET_SPEC = importlib.util.spec_from_file_location("owner_sealed_packet", PACKET_PATH)
assert PACKET_SPEC and PACKET_SPEC.loader
PACKET = importlib.util.module_from_spec(PACKET_SPEC)
sys.modules[PACKET_SPEC.name] = PACKET
PACKET_SPEC.loader.exec_module(PACKET)

CUSTODY_PATH = ROOT / "phoenix" / "ops-template" / "owner_custody_ceremony.py"
CUSTODY_SPEC = importlib.util.spec_from_file_location("owner_custody_ceremony", CUSTODY_PATH)
assert CUSTODY_SPEC and CUSTODY_SPEC.loader
CUSTODY = importlib.util.module_from_spec(CUSTODY_SPEC)
sys.modules[CUSTODY_SPEC.name] = CUSTODY
CUSTODY_SPEC.loader.exec_module(CUSTODY)

ATTEST_PATH = ROOT / "phoenix" / "ops-template" / "owner_custody_attestation.py"
ATTEST_SPEC = importlib.util.spec_from_file_location("owner_custody_attestation_v34", ATTEST_PATH)
assert ATTEST_SPEC and ATTEST_SPEC.loader
ATTEST = importlib.util.module_from_spec(ATTEST_SPEC)
ATTEST_SPEC.loader.exec_module(ATTEST)

CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_custody_attestation_checkpoint_v34.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v34.json"
CONTRACT = ROOT / "phoenix" / "ops-template" / "governance" / "OWNER_CUSTODY_ATTESTATION_CONTRACT.json"
POLICY = ROOT / "phoenix" / "export_policy.json"


def build_archive(path: Path, *, target: str) -> None:
    manifest_name = "PHOENIX_CORE_MANIFEST.json" if target == "Federation-Omega-Core" else "PHOENIX_OPS_MANIFEST.json"
    invariants = (
        {"workflow_count": 0, "runtime_state_count": 0, "migration_control_test_count": 0, "secret_marker_count": 0}
        if target == "Federation-Omega-Core"
        else {"active_workflow_count": 0, "legacy_workflow_count": 0, "long_lived_credentials": 0}
    )
    files = {
        manifest_name: json.dumps({"target": target, "invariants": invariants}, sort_keys=True, separators=(",", ":")).encode(),
        "README.md": target.encode(),
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, content in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))


class OwnerCustodyAttestationV34Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        core = self.root / "Federation-Omega-Core.tar.gz"
        ops = self.root / "Federation-Omega-Ops.tar.gz"
        build_archive(core, target="Federation-Omega-Core")
        build_archive(ops, target="Federation-Omega-Ops")
        self.packet = self.root / "owner-packet.json"
        PACKET.build_packet_candidate(
            core_archive=core,
            ops_archive=ops,
            output=self.packet,
            metadata={
                "source_repository": "mosianekk-lang/Federation-Omega",
                "source_sha": "a" * 40,
                "export_policy_version": "test",
                "core": {"sha256": PACKET.sha256_file(core), "size": core.stat().st_size},
                "ops": {"sha256": PACKET.sha256_file(ops), "size": ops.stat().st_size},
            },
        )
        fingerprint = hashlib.sha256(b"owner-controlled-offline-destination").hexdigest()
        manifest = self.root / "manifest.json"
        CUSTODY.prepare_manifest(
            packet_path=self.packet,
            output=manifest,
            owner_reference="OWNER-KKM",
            destination_label="OWNER-OFFLINE-VAULT",
            destination_fingerprint=fingerprint,
        )
        vault = self.root / "vault"
        vault.mkdir()
        self.copied_packet = vault / "owner-packet.json"
        self.receipt = self.root / "custody-receipt.json"
        CUSTODY.execute_local_copy(
            packet_path=self.packet,
            manifest_path=manifest,
            destination=self.copied_packet,
            receipt_output=self.receipt,
            confirmation=CUSTODY.CONFIRMATION,
        )
        self.issued = datetime(2026, 8, 5, 6, 0, tzinfo=timezone.utc)
        self.expires = self.issued + timedelta(minutes=10)
        self.challenge = self.root / "challenge.json"
        ATTEST.prepare_challenge(
            custody_receipt_path=self.receipt,
            copied_packet=self.copied_packet,
            output=self.challenge,
            execution_route="OWNER_ONLY_SEALED_PACKET",
            issued_at=self.issued,
            expires_at=self.expires,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_challenge_is_deterministic_bound_and_non_authoritative(self):
        second = self.root / "challenge-2.json"
        ATTEST.prepare_challenge(
            custody_receipt_path=self.receipt,
            copied_packet=self.copied_packet,
            output=second,
            execution_route="OWNER_ONLY_SEALED_PACKET",
            issued_at=self.issued,
            expires_at=self.expires,
        )
        self.assertEqual(self.challenge.read_bytes(), second.read_bytes())
        payload = ATTEST.verify_challenge(
            self.challenge,
            custody_receipt_path=self.receipt,
            copied_packet=self.copied_packet,
            now=self.issued,
        )
        self.assertFalse(payload["owner_controlled_custody_proven"])
        self.assertFalse(payload["owner_attestation_present"])
        self.assertFalse(payload["owner_authorization_present"])
        self.assertFalse(payload["provider_apply_performed"])

    def test_self_attestation_and_request_remain_non_authoritative(self):
        attestation = self.root / "attestation.json"
        created = ATTEST.create_attestation(
            challenge_path=self.challenge,
            custody_receipt_path=self.receipt,
            copied_packet=self.copied_packet,
            output=attestation,
            confirmation=ATTEST.CONFIRMATION,
            attested_at=self.issued + timedelta(minutes=1),
        )
        self.assertTrue(created["owner_controlled_custody_self_attested"])
        self.assertFalse(created["owner_identity_authenticity_proven"])
        verified = ATTEST.verify_attestation_content(
            attestation,
            challenge_path=self.challenge,
            custody_receipt_path=self.receipt,
            copied_packet=self.copied_packet,
            now=self.issued + timedelta(minutes=2),
        )
        self.assertFalse(verified["owner_controlled_custody_independently_proven"])
        self.assertFalse(verified["owner_authorization_present"])
        request = self.root / "authorization-request.json"
        compiled = ATTEST.compile_authorization_request(
            attestation_path=attestation,
            challenge_path=self.challenge,
            custody_receipt_path=self.receipt,
            copied_packet=self.copied_packet,
            output=request,
            now=self.issued + timedelta(minutes=2),
        )
        self.assertEqual(
            "OWNER_IDENTITY_PROOF_AND_EXACT_SHORT_LIVED_AUTHORIZATION_DECISION_REQUIRED",
            compiled["status"],
        )
        self.assertFalse(compiled["owner_authorization_present"])
        self.assertFalse(compiled["provider_authority_present"])
        self.assertFalse(compiled["provider_apply_performed"])

    def test_tamper_expiry_and_binding_drift_fail_closed(self):
        with self.assertRaises(ATTEST.OwnerCustodyAttestationError):
            ATTEST.create_attestation(
                challenge_path=self.challenge,
                custody_receipt_path=self.receipt,
                copied_packet=self.copied_packet,
                output=self.root / "bad.json",
                confirmation="yes",
                attested_at=self.issued + timedelta(minutes=1),
            )
        with self.assertRaises(ATTEST.OwnerCustodyAttestationError):
            ATTEST.verify_challenge(
                self.challenge,
                custody_receipt_path=self.receipt,
                copied_packet=self.copied_packet,
                now=self.expires + timedelta(seconds=1),
            )
        payload = json.loads(self.challenge.read_text())
        payload["execution_route"] = "DRIFT"
        self.challenge.write_text(json.dumps(payload))
        with self.assertRaises(ATTEST.OwnerCustodyAttestationError):
            ATTEST.verify_challenge(
                self.challenge,
                custody_receipt_path=self.receipt,
                copied_packet=self.copied_packet,
                now=self.issued,
            )

    def test_contract_policy_checkpoint_projection_and_truth_boundary(self):
        contract = json.loads(CONTRACT.read_text())
        policy = json.loads(POLICY.read_text())
        self.assertEqual("PREPARED_NOT_EXECUTED_OWNER_RESERVED", contract["status"])
        self.assertFalse(contract["controls"]["owner_control_inferred_from_self_attestation"])
        self.assertFalse(contract["controls"]["owner_authorization_created"])
        self.assertFalse(contract["controls"]["provider_apply_performed"])
        self.assertIn("owner_custody_attestation.py", policy["ops"]["required_files"])
        self.assertIn(
            "governance/OWNER_CUSTODY_ATTESTATION_CONTRACT.json",
            policy["ops"]["required_files"],
        )
        checkpoint = json.loads(CHECKPOINT.read_text())
        projection = json.loads(PROJECTION.read_text())
        for payload, field in ((checkpoint, "checkpoint_sha256"), (projection, "projection_sha256")):
            body = dict(payload)
            claimed = body.pop(field)
            calculated = hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            self.assertEqual(claimed, calculated)
        self.assertEqual([f"C{i:02d}" for i in range(1, 16)], projection["dependency_order"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        self.assertFalse(checkpoint["attestation_truth"]["owner_attestation_present"])
        self.assertFalse(checkpoint["commercial_truth"]["full_commercial_maturity"])


if __name__ == "__main__":
    unittest.main()
