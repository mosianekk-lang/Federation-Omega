from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "phoenix" / "ops-template" / "owner_sealed_packet.py"
SPEC = importlib.util.spec_from_file_location("owner_sealed_packet_v32", MODULE_PATH)
assert SPEC and SPEC.loader
PACKET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKET)
CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_sealed_packet_candidate_checkpoint_v32.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v32.json"


def build_archive(path: Path, *, target: str, extra: dict[str, bytes] | None = None) -> None:
    manifest_name = (
        "PHOENIX_CORE_MANIFEST.json"
        if target == "Federation-Omega-Core"
        else "PHOENIX_OPS_MANIFEST.json"
    )
    invariants = (
        {
            "workflow_count": 0,
            "runtime_state_count": 0,
            "migration_control_test_count": 0,
            "secret_marker_count": 0,
        }
        if target == "Federation-Omega-Core"
        else {
            "active_workflow_count": 0,
            "legacy_workflow_count": 0,
            "long_lived_credentials": 0,
        }
    )
    files = {
        manifest_name: json.dumps(
            {"target": target, "invariants": invariants},
            sort_keys=True,
            separators=(",", ":"),
        ).encode(),
        "README.md": target.encode(),
    }
    files.update(extra or {})
    with tarfile.open(path, "w:gz") as archive:
        for name, content in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))


class OwnerSealedPacketCandidateV32Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core = self.root / "Federation-Omega-Core.tar.gz"
        self.ops = self.root / "Federation-Omega-Ops.tar.gz"
        build_archive(self.core, target="Federation-Omega-Core")
        build_archive(self.ops, target="Federation-Omega-Ops")
        self.metadata = {
            "source_repository": "mosianekk-lang/Federation-Omega",
            "source_sha": "a" * 40,
            "export_policy_version": "test",
            "core": {"sha256": PACKET.sha256_file(self.core), "size": self.core.stat().st_size},
            "ops": {"sha256": PACKET.sha256_file(self.ops), "size": self.ops.stat().st_size},
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_packet_is_deterministic_round_trip_verified_and_non_authoritative(self):
        first = self.root / "first.json"
        second = self.root / "second.json"
        one = PACKET.build_packet_candidate(
            core_archive=self.core,
            ops_archive=self.ops,
            output=first,
            metadata=self.metadata,
        )
        two = PACKET.build_packet_candidate(
            core_archive=self.core,
            ops_archive=self.ops,
            output=second,
            metadata=self.metadata,
        )
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(one["packet_sha256"], two["packet_sha256"])
        verified = PACKET.verify_packet_candidate(first)
        self.assertFalse(verified["provider_apply_performed"])
        self.assertFalse(verified["external_commercial_gate_advanced"])
        payload = json.loads(first.read_text())
        self.assertEqual("OWNER_CONTROLLED_CUSTODY_NOT_PROVEN", payload["custody_state"])
        self.assertEqual("OWNER_AUTHORIZATION_NOT_PRESENT", payload["authority_state"])
        self.assertEqual(0, payload["commercial_truth"]["verified_live_revenue_events"])

    def test_packet_and_archive_tampering_fail_closed(self):
        output = self.root / "packet.json"
        PACKET.build_packet_candidate(
            core_archive=self.core,
            ops_archive=self.ops,
            output=output,
            metadata=self.metadata,
        )
        payload = json.loads(output.read_text())
        payload["commercial_truth"]["customer_demand"] = "VERIFIED"
        output.write_text(json.dumps(payload))
        with self.assertRaises(PACKET.OwnerSealedPacketError):
            PACKET.verify_packet_candidate(output)

        altered = dict(self.metadata)
        altered["core"] = dict(altered["core"])
        altered["core"]["sha256"] = "0" * 64
        with self.assertRaises(PACKET.OwnerSealedPacketError):
            PACKET.build_packet_candidate(
                core_archive=self.core,
                ops_archive=self.ops,
                output=self.root / "bad.json",
                metadata=altered,
            )

    def test_workflows_symlinks_and_invariant_drift_are_rejected(self):
        unsafe = self.root / "unsafe.tar.gz"
        build_archive(
            unsafe,
            target="Federation-Omega-Ops",
            extra={"nested/.github/workflows/apply.yml": b"name: unsafe"},
        )
        with self.assertRaises(PACKET.OwnerSealedPacketError):
            PACKET.inspect_archive(unsafe.read_bytes(), target="Federation-Omega-Ops")

        symlink = self.root / "symlink.tar.gz"
        with tarfile.open(symlink, "w:gz") as archive:
            info = tarfile.TarInfo("PHOENIX_OPS_MANIFEST.json")
            manifest = json.dumps({
                "target": "Federation-Omega-Ops",
                "invariants": {"active_workflow_count": 0, "legacy_workflow_count": 0, "long_lived_credentials": 0},
            }).encode()
            info.size = len(manifest)
            archive.addfile(info, io.BytesIO(manifest))
            link = tarfile.TarInfo("unsafe-link")
            link.type = tarfile.SYMTYPE
            link.linkname = "../outside"
            archive.addfile(link)
        with self.assertRaises(PACKET.OwnerSealedPacketError):
            PACKET.inspect_archive(symlink.read_bytes(), target="Federation-Omega-Ops")

    def test_checkpoint_projection_hashes_dependency_order_and_truth(self):
        checkpoint = json.loads(CHECKPOINT.read_text())
        projection = json.loads(PROJECTION.read_text())
        for payload, field in (
            (checkpoint, "checkpoint_sha256"),
            (projection, "projection_sha256"),
        ):
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


if __name__ == "__main__":
    unittest.main()
