from __future__ import annotations

import importlib.util
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

import owner_execution_evidence_intake as INTAKE
import owner_execution_handoff as HANDOFF
import owner_sealed_packet as PACKET

MODULE_PATH = OPS / "owner_execution_step1_binding.py"
SPEC = importlib.util.spec_from_file_location(
    "owner_execution_step1_binding_v39", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CAPABILITY_RELEASE = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_evidence_intake_release_receipt_v38.json"
)
V37_RELEASE = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_handoff_release_receipt_v37.json"
)
V36_RELEASE = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_attested_authorization_release_receipt_v36.json"
)
CONTRACT = OPS / "governance" / "OWNER_EXECUTION_STEP1_BINDING_CONTRACT.json"
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_step1_binding_checkpoint_v39.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v39.json"
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
    manifest = {"target": target, "invariants": invariants}
    payload = json.dumps(manifest, sort_keys=True).encode("utf-8")
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(manifest_name)
        info.size = len(payload)
        info.mtime = 0
        archive.addfile(info, io.BytesIO(payload))


class OwnerExecutionStep1BindingV39Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.capability = load(CAPABILITY_RELEASE)
        self.v37 = load(V37_RELEASE)
        self.v36 = load(V36_RELEASE)
        self.now = datetime(2026, 8, 5, 8, 37, 0, tzinfo=timezone.utc)
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
            "export_policy_version": "1.0.19",
            "core": {
                "sha256": PACKET.sha256_file(self.core),
                "size": self.core.stat().st_size,
            },
            "ops": {
                "sha256": PACKET.sha256_file(self.ops),
                "size": self.ops.stat().st_size,
            },
        }
        packet_result = PACKET.build_packet_candidate(
            core_archive=self.core,
            ops_archive=self.ops,
            output=self.packet,
            metadata=metadata,
        )
        self.v37["provider_proof"]["owner_packet_sha256"] = packet_result[
            "packet_sha256"
        ]
        self.v37["provider_proof"]["owner_packet_file_sha256"] = packet_result[
            "file_sha256"
        ]
        self.v37 = rehash(self.v37, "receipt_sha256")
        self.handoff = HANDOFF.build_handoff(
            release_receipt=self.v36,
            current_source_sha=SOURCE_SHA,
            owner_login="mosianekk-lang",
            repository_full_name="mosianekk-lang/Federation-Omega",
            owner_packet_sha256=packet_result["packet_sha256"],
            generated_at=self.now,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self) -> dict:
        return MODULE.build_step1_evidence(
            capability_release=self.capability,
            predecessor_release=self.v37,
            handoff=self.handoff,
            owner_packet_path=self.packet,
            current_source_sha=SOURCE_SHA,
            recorded_at=self.now,
        )

    def test_step1_evidence_is_accepted_by_v38_intake(self):
        evidence = self.build()
        self.assertEqual(1, evidence["sequence"])
        self.assertEqual("A1_INTERNAL", evidence["authority"])
        self.assertEqual("INTERNAL_HASH_BOUND", evidence["evidence_mode"])
        self.assertFalse(evidence["owner_attested"])
        self.assertFalse(evidence["provider_native"])
        verification = MODULE.verify_step1_evidence(evidence, handoff=self.handoff)
        self.assertEqual(2, verification["next_eligible_step"])
        dossier = INTAKE.build_dossier(
            release_receipt=self.v37,
            handoff=self.handoff,
            evidence_chain=[evidence],
            current_source_sha=SOURCE_SHA,
            generated_at=self.now,
        )
        self.assertEqual(1, dossier["admitted_evidence_count"])
        self.assertEqual(2, dossier["next_eligible_step"]["sequence"])
        self.assertTrue(dossier["next_eligible_step"]["owner_reserved"])
        self.assertFalse(dossier["owner_execution_proven"])
        self.assertFalse(dossier["provider_apply_proven"])

    def test_packet_file_tampering_fails_closed(self):
        self.packet.write_bytes(self.packet.read_bytes() + b" ")
        with self.assertRaises(MODULE.OwnerExecutionStep1BindingError):
            self.build()

    def test_release_packet_binding_drift_fails_closed(self):
        self.v37["provider_proof"]["owner_packet_sha256"] = "0" * 64
        self.v37 = rehash(self.v37, "receipt_sha256")
        with self.assertRaises(MODULE.OwnerExecutionStep1BindingError):
            self.build()

    def test_packet_source_binding_drift_fails_closed(self):
        payload = load(self.packet)
        payload["source_sha"] = "f" * 40
        payload["packet_sha256"] = PACKET.sha256_bytes(
            PACKET.canonical_bytes(
                {key: value for key, value in payload.items() if key != "packet_sha256"}
            )
        )
        self.packet.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        self.v37["provider_proof"]["owner_packet_sha256"] = payload["packet_sha256"]
        self.v37["provider_proof"]["owner_packet_file_sha256"] = PACKET.sha256_file(
            self.packet
        )
        self.v37 = rehash(self.v37, "receipt_sha256")
        self.handoff = HANDOFF.build_handoff(
            release_receipt=self.v36,
            current_source_sha=SOURCE_SHA,
            owner_login="mosianekk-lang",
            repository_full_name="mosianekk-lang/Federation-Omega",
            owner_packet_sha256=payload["packet_sha256"],
            generated_at=self.now,
        )
        with self.assertRaises(MODULE.OwnerExecutionStep1BindingError):
            self.build()

    def test_capability_release_overclaim_fails_closed(self):
        self.capability["commercial_truth"]["verified_live_revenue_events"] = 1
        self.capability = rehash(self.capability, "receipt_sha256")
        with self.assertRaises(MODULE.OwnerExecutionStep1BindingError):
            self.build()

    def test_evidence_tampering_fails_closed(self):
        evidence = self.build()
        evidence["provider_native"] = True
        evidence = rehash(evidence, "evidence_sha256")
        with self.assertRaises(MODULE.OwnerExecutionStep1BindingError):
            MODULE.verify_step1_evidence(evidence, handoff=self.handoff)

    def test_contract_checkpoint_projection_and_export_truth(self):
        contract = load(CONTRACT)
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        policy = load(POLICY)
        MODULE._verify_self_hash(checkpoint, "checkpoint_sha256", "checkpoint")
        MODULE._verify_self_hash(projection, "projection_sha256", "projection")
        self.assertEqual(
            "INTERNAL_BINDING_CAPABILITY_ONLY_NOT_OWNER_OR_PROVIDER_PROOF",
            contract["status"],
        )
        self.assertFalse(contract["controls"]["owner_action_allowed"])
        self.assertFalse(contract["controls"]["provider_apply_allowed"])
        self.assertEqual(
            "OWNER_EXECUTION_STEP1_BINDING_IMPLEMENTED_PROVIDER_PROOF_REQUIRED_"
            "OWNER_CUSTODY_ACTION_REQUIRED",
            checkpoint["status"],
        )
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        required = set(policy["ops"]["required_files"])
        self.assertEqual("1.0.19", policy["version"])
        self.assertIn("owner_execution_step1_binding.py", required)
        self.assertIn(
            "governance/OWNER_EXECUTION_STEP1_BINDING_CONTRACT.json", required
        )


if __name__ == "__main__":
    unittest.main()
