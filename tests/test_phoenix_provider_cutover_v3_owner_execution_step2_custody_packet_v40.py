from __future__ import annotations

import io
import json
import sys
import tarfile
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "phoenix" / "ops-template"
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))

import owner_execution_handoff as HANDOFF
import owner_execution_step1_binding as STEP1
import owner_execution_step2_custody_packet as MODULE
import owner_sealed_packet as PACKET

V40_CONTRACT = OPS / "governance" / "OWNER_EXECUTION_STEP2_CUSTODY_PACKET_CONTRACT.json"
V39_RELEASE = ROOT / "alpha_omega_commercial" / "phoenix_owner_execution_step1_binding_release_receipt_v39.json"
V38_RELEASE = ROOT / "alpha_omega_commercial" / "phoenix_owner_execution_evidence_intake_release_receipt_v38.json"
V37_RELEASE = ROOT / "alpha_omega_commercial" / "phoenix_owner_execution_handoff_release_receipt_v37.json"
V36_RELEASE = ROOT / "alpha_omega_commercial" / "phoenix_provider_attested_authorization_release_receipt_v36.json"
CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_execution_step2_custody_packet_checkpoint_v40.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v40.json"
POLICY = ROOT / "phoenix" / "export_policy.json"
SOURCE_SHA = "36916cb0e26813e1bfb57a3c1a2993d82e7fd425"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rehash(payload: dict, field: str) -> dict:
    body = dict(payload)
    body.pop(field, None)
    body[field] = MODULE.canonical_sha256(body)
    return body


def write_archive(path: Path, *, target: str) -> None:
    manifest_name = "PHOENIX_CORE_MANIFEST.json" if target == "Federation-Omega-Core" else "PHOENIX_OPS_MANIFEST.json"
    invariants = (
        {"workflow_count": 0, "runtime_state_count": 0, "migration_control_test_count": 0, "secret_marker_count": 0}
        if target == "Federation-Omega-Core"
        else {"active_workflow_count": 0, "legacy_workflow_count": 0, "long_lived_credentials": 0}
    )
    payload = json.dumps({"target": target, "invariants": invariants}, sort_keys=True).encode("utf-8")
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(manifest_name)
        info.size = len(payload)
        info.mtime = 0
        archive.addfile(info, io.BytesIO(payload))


class OwnerExecutionStep2CustodyPacketV40Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.v39 = load(V39_RELEASE)
        self.v38 = load(V38_RELEASE)
        self.v37 = load(V37_RELEASE)
        self.v36 = load(V36_RELEASE)
        self.now = datetime(2026, 8, 5, 9, 32, 0, tzinfo=timezone.utc)
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.core = self.base / "Federation-Omega-Core.tar.gz"
        self.ops = self.base / "Federation-Omega-Ops.tar.gz"
        self.packet = self.base / "phoenix-owner-sealed-packet.json"
        write_archive(self.core, target="Federation-Omega-Core")
        write_archive(self.ops, target="Federation-Omega-Ops")
        metadata = {
            "source_repository": "mosianekk-lang/Federation-Omega",
            "source_sha": self.v37["merged_main_sha"],
            "export_policy_version": "1.0.20",
            "core": {"sha256": PACKET.sha256_file(self.core), "size": self.core.stat().st_size},
            "ops": {"sha256": PACKET.sha256_file(self.ops), "size": self.ops.stat().st_size},
        }
        packet_result = PACKET.build_packet_candidate(core_archive=self.core, ops_archive=self.ops, output=self.packet, metadata=metadata)
        for receipt in (self.v37, self.v39):
            receipt["provider_proof"]["owner_packet_sha256"] = packet_result["packet_sha256"]
            receipt["provider_proof"]["owner_packet_file_sha256"] = packet_result["file_sha256"]
            receipt.update(rehash(receipt, "receipt_sha256"))
        self.handoff = HANDOFF.build_handoff(
            release_receipt=self.v36,
            current_source_sha=SOURCE_SHA,
            owner_login="mosianekk-lang",
            repository_full_name="mosianekk-lang/Federation-Omega",
            owner_packet_sha256=packet_result["packet_sha256"],
            generated_at=self.now,
        )
        self.step1 = STEP1.build_step1_evidence(
            capability_release=self.v38,
            predecessor_release=self.v37,
            handoff=self.handoff,
            owner_packet_path=self.packet,
            current_source_sha=SOURCE_SHA,
            recorded_at=self.now,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self) -> dict:
        return MODULE.build_step2_custody_packet(
            release_receipt=self.v39,
            handoff=self.handoff,
            step1_evidence=self.step1,
            owner_packet_path=self.packet,
            handoff_source_sha=SOURCE_SHA,
            generated_at=self.now,
        )

    def test_packet_is_hash_bound_dependency_ordered_and_non_executing(self):
        result = self.build()
        self.assertEqual(MODULE.PACKET_STATUS, result["status"])
        self.assertEqual(2, result["step"]["sequence"])
        self.assertEqual("OWNER_RESERVED", result["step"]["authority"])
        self.assertFalse(result["required_owner_inputs"]["values_present"])
        self.assertEqual("ESTABLISH OWNER-CONTROLLED CUSTODY", result["copy_command_template"][-1])
        self.assertTrue(result["owner_execution_required"])
        self.assertFalse(result["owner_action_performed"])
        self.assertFalse(result["provider_apply_performed"])
        verified = MODULE.verify_step2_custody_packet(result)
        self.assertEqual(3, verified["next_eligible_step_after_owner_execution"])

    def test_no_owner_values_are_prepopulated(self):
        result = self.build()
        encoded = json.dumps(result, sort_keys=True)
        self.assertNotIn(str(self.base), encoded)
        self.assertNotIn("mosianekk@gmail.com", encoded)
        self.assertFalse(result["owner_input_values_recorded"])

    def test_release_commercial_overclaim_fails_closed(self):
        self.v39["commercial_truth"]["verified_live_revenue_events"] = 1
        self.v39 = rehash(self.v39, "receipt_sha256")
        with self.assertRaises(MODULE.OwnerExecutionStep2CustodyPacketError):
            self.build()

    def test_step1_evidence_tamper_fails_closed(self):
        self.step1["provider_native"] = True
        self.step1 = rehash(self.step1, "evidence_sha256")
        with self.assertRaises(MODULE.OwnerExecutionStep2CustodyPacketError):
            self.build()

    def test_step2_order_drift_fails_closed(self):
        self.handoff["ordered_steps"][1]["sequence"] = 3
        self.handoff = rehash(self.handoff, "handoff_sha256")
        with self.assertRaises(MODULE.OwnerExecutionStep2CustodyPacketError):
            self.build()

    def test_owner_packet_tamper_fails_closed(self):
        self.packet.write_bytes(self.packet.read_bytes() + b" ")
        with self.assertRaises(MODULE.OwnerExecutionStep2CustodyPacketError):
            self.build()

    def test_execution_packet_overclaim_fails_closed(self):
        result = self.build()
        result["owner_action_performed"] = True
        result = rehash(result, "execution_packet_sha256")
        with self.assertRaises(MODULE.OwnerExecutionStep2CustodyPacketError):
            MODULE.verify_step2_custody_packet(result)

    def test_contract_checkpoint_projection_and_export_truth(self):
        contract = load(V40_CONTRACT)
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        policy = load(POLICY)
        MODULE._verify_self_hash(checkpoint, "checkpoint_sha256", "checkpoint")
        MODULE._verify_self_hash(projection, "projection_sha256", "projection")
        self.assertEqual("NON_EXECUTING_OWNER_HANDOFF_ONLY", contract["status"])
        self.assertFalse(contract["controls"]["owner_action_allowed"])
        self.assertFalse(contract["controls"]["provider_apply_allowed"])
        self.assertEqual(
            "OWNER_EXECUTION_STEP2_CUSTODY_PACKET_PROVIDER_PROOF_VERIFIED_OWNER_EXECUTION_REQUIRED",
            checkpoint["status"],
        )
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        required = set(policy["ops"]["required_files"])
        self.assertEqual("1.0.20", policy["version"])
        self.assertIn("owner_execution_step2_custody_packet.py", required)
        self.assertIn("governance/OWNER_EXECUTION_STEP2_CUSTODY_PACKET_CONTRACT.json", required)


if __name__ == "__main__":
    unittest.main()
