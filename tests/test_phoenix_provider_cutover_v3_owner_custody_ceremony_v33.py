from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = ROOT / "phoenix" / "ops-template" / "owner_sealed_packet.py"
PACKET_SPEC = importlib.util.spec_from_file_location("owner_sealed_packet", PACKET_PATH)
assert PACKET_SPEC and PACKET_SPEC.loader
PACKET = importlib.util.module_from_spec(PACKET_SPEC)
sys.modules[PACKET_SPEC.name] = PACKET
PACKET_SPEC.loader.exec_module(PACKET)

CUSTODY_PATH = ROOT / "phoenix" / "ops-template" / "owner_custody_ceremony.py"
CUSTODY_SPEC = importlib.util.spec_from_file_location("owner_custody_ceremony_v33", CUSTODY_PATH)
assert CUSTODY_SPEC and CUSTODY_SPEC.loader
CUSTODY = importlib.util.module_from_spec(CUSTODY_SPEC)
CUSTODY_SPEC.loader.exec_module(CUSTODY)

CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_custody_ceremony_checkpoint_v33.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v33.json"
CONTRACT = ROOT / "phoenix" / "ops-template" / "governance" / "OWNER_CUSTODY_CEREMONY_CONTRACT.json"
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


class OwnerCustodyCeremonyV33Tests(unittest.TestCase):
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
        self.fingerprint = hashlib.sha256(b"owner-controlled-offline-destination").hexdigest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def prepare(self) -> Path:
        manifest = self.root / "manifest.json"
        CUSTODY.prepare_manifest(
            packet_path=self.packet,
            output=manifest,
            owner_reference="OWNER-KKM",
            destination_label="OWNER-OFFLINE-VAULT",
            destination_fingerprint=self.fingerprint,
        )
        return manifest

    def test_manifest_is_deterministic_hash_bound_and_non_authoritative(self):
        first = self.prepare()
        second = self.root / "manifest-2.json"
        CUSTODY.prepare_manifest(
            packet_path=self.packet,
            output=second,
            owner_reference="OWNER-KKM",
            destination_label="OWNER-OFFLINE-VAULT",
            destination_fingerprint=self.fingerprint,
        )
        self.assertEqual(first.read_bytes(), second.read_bytes())
        payload = CUSTODY.verify_manifest(first, packet_path=self.packet)
        self.assertFalse(payload["owner_controlled_custody_proven"])
        self.assertFalse(payload["owner_authorization_present"])
        self.assertFalse(payload["provider_apply_performed"])
        self.assertTrue(payload["owner_attestation_required"])

    def test_copy_is_atomic_private_idempotent_and_attestation_bound(self):
        manifest = self.prepare()
        vault = self.root / "vault"
        vault.mkdir()
        destination = vault / "owner-packet.json"
        receipt = self.root / "receipt.json"
        first = CUSTODY.execute_local_copy(
            packet_path=self.packet,
            manifest_path=manifest,
            destination=destination,
            receipt_output=receipt,
            confirmation=CUSTODY.CONFIRMATION,
        )
        self.assertEqual(0o600, stat.S_IMODE(destination.stat().st_mode))
        self.assertFalse(first["idempotent_replay"])
        self.assertFalse(first["owner_controlled_custody_proven"])
        self.assertTrue(first["owner_attestation_required"])
        second = CUSTODY.execute_local_copy(
            packet_path=self.packet,
            manifest_path=manifest,
            destination=destination,
            receipt_output=receipt,
            confirmation=CUSTODY.CONFIRMATION,
        )
        self.assertTrue(second["idempotent_replay"])
        CUSTODY.verify_receipt(receipt, copied_packet=destination)

    def test_confirmation_tamper_symlink_and_permission_drift_fail_closed(self):
        manifest = self.prepare()
        vault = self.root / "vault"
        vault.mkdir()
        with self.assertRaises(CUSTODY.OwnerCustodyCeremonyError):
            CUSTODY.execute_local_copy(
                packet_path=self.packet,
                manifest_path=manifest,
                destination=vault / "packet.json",
                receipt_output=self.root / "receipt.json",
                confirmation="yes",
            )
        payload = json.loads(manifest.read_text())
        payload["destination_label"] = "DRIFT"
        manifest.write_text(json.dumps(payload))
        with self.assertRaises(CUSTODY.OwnerCustodyCeremonyError):
            CUSTODY.verify_manifest(manifest, packet_path=self.packet)

        manifest = self.prepare()
        outside = self.root / "outside.json"
        outside.write_text("outside")
        symlink = vault / "symlink.json"
        try:
            symlink.symlink_to(outside)
        except (OSError, NotImplementedError):
            symlink = None
        if symlink is not None:
            with self.assertRaises(CUSTODY.OwnerCustodyCeremonyError):
                CUSTODY.execute_local_copy(
                    packet_path=self.packet,
                    manifest_path=manifest,
                    destination=symlink,
                    receipt_output=self.root / "symlink-receipt.json",
                    confirmation=CUSTODY.CONFIRMATION,
                )

        destination = vault / "safe.json"
        receipt = self.root / "safe-receipt.json"
        CUSTODY.execute_local_copy(
            packet_path=self.packet,
            manifest_path=manifest,
            destination=destination,
            receipt_output=receipt,
            confirmation=CUSTODY.CONFIRMATION,
        )
        os.chmod(destination, 0o644)
        with self.assertRaises(CUSTODY.OwnerCustodyCeremonyError):
            CUSTODY.verify_receipt(receipt, copied_packet=destination)

    def test_contract_policy_checkpoint_projection_and_truth_boundary(self):
        contract = json.loads(CONTRACT.read_text())
        policy = json.loads(POLICY.read_text())
        self.assertEqual("PREPARED_NOT_EXECUTED_OWNER_RESERVED", contract["status"])
        self.assertFalse(contract["controls"]["owner_control_inferred_from_copy"])
        self.assertFalse(contract["controls"]["provider_apply_performed"])
        self.assertIn("owner_custody_ceremony.py", policy["ops"]["required_files"])
        self.assertIn("governance/OWNER_CUSTODY_CEREMONY_CONTRACT.json", policy["ops"]["required_files"])
        checkpoint = json.loads(CHECKPOINT.read_text())
        projection = json.loads(PROJECTION.read_text())
        for payload, field in ((checkpoint, "checkpoint_sha256"), (projection, "projection_sha256")):
            body = dict(payload)
            claimed = body.pop(field)
            calculated = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(claimed, calculated)
        self.assertEqual([f"C{i:02d}" for i in range(1, 16)], projection["dependency_order"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        self.assertFalse(checkpoint["custody_truth"]["owner_controlled_custody_proven"])
        self.assertFalse(checkpoint["commercial_truth"]["full_commercial_maturity"])


if __name__ == "__main__":
    unittest.main()
