from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_owner_custody_attestation_checkpoint_v34.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v34.json"
RECEIPT = ROOT / "alpha_omega_commercial" / "phoenix_owner_custody_attestation_release_receipt_v34.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_hash(payload: dict, field: str) -> None:
    body = dict(payload)
    claimed = body.pop(field)
    calculated = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert claimed == calculated


class OwnerCustodyAttestationReleaseV34Tests(unittest.TestCase):
    def test_checkpoint_projection_and_receipt_are_hash_bound(self):
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        receipt = load(RECEIPT)
        verify_hash(checkpoint, "checkpoint_sha256")
        verify_hash(projection, "projection_sha256")
        verify_hash(receipt, "receipt_sha256")
        self.assertEqual(
            "OWNER_CUSTODY_ATTESTATION_INTAKE_PROVIDER_PROOF_VERIFIED_OWNER_EXECUTION_AND_PROVIDER_AUTHENTICATED_ATTESTATION_REQUIRED",
            checkpoint["status"],
        )
        self.assertEqual(checkpoint["status"], receipt["status"])
        self.assertIn("PROVIDER_PROOF_VERIFIED", projection["canonical_status"])

    def test_provider_native_admission_and_current_main_proof_are_exact(self):
        checkpoint = load(CHECKPOINT)
        proof = checkpoint["provider_proof"]
        self.assertEqual(30980751596, proof["airlock_run"])
        self.assertEqual(92224436309, proof["airlock_job"])
        self.assertEqual(8920031248, proof["airlock_artifact_id"])
        self.assertEqual(
            "74c2b8391b1a658613bf2bd6879d20aff7ced114c6ec05322fb7c0988cdc906e",
            proof["airlock_artifact_sha256"],
        )
        self.assertEqual(30980799234, proof["phoenix_run"])
        self.assertEqual(92224581067, proof["phoenix_job"])
        self.assertEqual(
            "4b47abf0b97305cae58f2c57c5706675b3770909",
            proof["merged_main_sha"],
        )
        self.assertEqual(0, proof["core_active_workflows"])
        self.assertEqual(0, proof["ops_active_workflows"])
        self.assertEqual(0, proof["runtime_bytecode"])
        self.assertTrue(proof["ops_attestation_engine_included"])
        self.assertTrue(proof["ops_attestation_contract_included"])
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        self.assertEqual(0, proof["unexpected_active_workflows"])

    def test_drive_release_and_external_truth_remain_fail_closed(self):
        checkpoint = load(CHECKPOINT)
        drive = checkpoint["drive_release"]
        self.assertEqual("1VMIerwIa7hEKefjtuknz9oLSZa5y8J3ZQmbW33cuspQ", drive["file_id"])
        self.assertEqual(4863, drive["export_size"])
        self.assertEqual(
            "db4d281a9f45ab6c0e7d0b03d03cdd76ca47bc2de938d4a514f0c95589a5feba",
            drive["export_sha256"],
        )
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual("VERIFIED", drive["readback"])
        truth = checkpoint["commercial_truth"]
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["customer_demand"])
        self.assertEqual("NOT_PROVEN", truth["cloud_run_operation"])
        self.assertEqual(0, truth["verified_live_revenue_events"])
        self.assertFalse(truth["full_commercial_maturity"])
        custody = checkpoint["attestation_truth"]
        self.assertFalse(custody["owner_controlled_custody_proven"])
        self.assertFalse(custody["owner_attestation_present"])
        self.assertFalse(custody["owner_identity_authenticity_proven"])
        self.assertFalse(custody["owner_authorization_present"])

    def test_dependency_order_service_priority_and_provider_boundary(self):
        projection = load(PROJECTION)
        self.assertEqual([f"C{i:02d}" for i in range(1, 16)], projection["dependency_order"])
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        plane = projection["provider_execution_plane"]
        self.assertIn("PROVIDER_BLOCKED", plane["private_github_route"])
        self.assertFalse(plane["provider_apply_performed"])
        checkpoint = load(CHECKPOINT)
        provider = checkpoint["provider_authority_readback"]
        self.assertEqual("SELECTED_REPOSITORY_ONLY", provider["installation_repository_scope_assessment"])
        self.assertEqual(["mosianekk-lang/Federation-Omega"], provider["installed_repositories"])
        self.assertEqual("NOT_FOUND_NOT_CLAIMED_CREATED", provider["target_core_repository"])
        self.assertEqual("NOT_FOUND_NOT_CLAIMED_CREATED", provider["target_ops_repository"])


if __name__ == "__main__":
    unittest.main()
