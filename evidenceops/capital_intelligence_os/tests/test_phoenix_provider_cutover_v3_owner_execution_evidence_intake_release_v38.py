from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_evidence_intake_checkpoint_v38.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v38.json"
RECEIPT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_evidence_intake_release_receipt_v38.json"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_hash(payload: dict, field: str) -> None:
    body = dict(payload)
    claimed = body.pop(field)
    calculated = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert claimed == calculated


class OwnerExecutionEvidenceIntakeReleaseV38Tests(unittest.TestCase):
    def test_checkpoint_projection_and_receipt_are_hash_bound(self):
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        receipt = load(RECEIPT)
        verify_hash(checkpoint, "checkpoint_sha256")
        verify_hash(projection, "projection_sha256")
        verify_hash(receipt, "receipt_sha256")
        self.assertEqual(
            checkpoint["checkpoint_sha256"], receipt["checkpoint_sha256"]
        )
        self.assertEqual(
            projection["projection_sha256"], receipt["projection_sha256"]
        )
        self.assertEqual(
            "OWNER_EXECUTION_EVIDENCE_INTAKE_PROVIDER_PROOF_VERIFIED_"
            "OWNER_ACTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED",
            receipt["status"],
        )

    def test_provider_native_admission_current_main_and_export_are_exact(self):
        receipt = load(RECEIPT)
        proof = receipt["provider_proof"]
        self.assertEqual(286, receipt["implementation_pr"])
        self.assertEqual(
            "f3c32e8b5f1afd00d5b531f14a3d88d8b055bfae",
            receipt["implementation_pr_head"],
        )
        self.assertEqual(
            "3de685cfca8790eecbc3cfd06c71a5e2a558b57e",
            receipt["merged_main_sha"],
        )
        self.assertEqual(30988270421, proof["airlock_run"])
        self.assertEqual(92248032578, proof["airlock_job"])
        self.assertEqual(8922995202, proof["airlock_artifact_id"])
        self.assertEqual(
            "d60e1ec2310c469025e3a04f9e23c050fb9c8e1acc0eb36edc1f0ec0213018f4",
            proof["airlock_artifact_sha256"],
        )
        self.assertEqual(
            "c5f488fa25b70790ba3d81fa7d0440d42f21063846c74855fdee9f2d12da9cb7",
            proof["source_provenance_receipt_sha256"],
        )
        self.assertEqual(0, proof["airlock_findings"])
        self.assertEqual(0, proof["changed_workflows"])
        self.assertEqual(0, proof["unadmitted_commits"])
        self.assertEqual(238, proof["provider_v3_family_tests_passed"])
        self.assertEqual(30988426624, proof["phoenix_run"])
        self.assertEqual(92248547069, proof["phoenix_job"])
        self.assertEqual(8923061865, proof["cutover_artifact_id"])
        self.assertEqual(
            "e4b5fb80dcd4aa1bc34d0bf1fe1f315b42f3bfb99fd94dc4d05d95cd8120773b",
            proof["cutover_artifact_sha256"],
        )
        self.assertEqual(8923061070, proof["execution_freeze_artifact_id"])
        self.assertEqual(
            "ed44495664a944a14ba7476a99ebc157f77d137f62672b556251b111b0ee544b",
            proof["execution_freeze_artifact_sha256"],
        )
        self.assertEqual(
            "66e7529d5418703af9926e1375309ee62cac3b2e3796deb99430ecd31d8c7c88",
            proof["core_archive_sha256"],
        )
        self.assertEqual(1184, proof["core_member_count"])
        self.assertEqual(0, proof["core_active_workflows"])
        self.assertEqual(0, proof["core_runtime_bytecode"])
        self.assertEqual(
            "fc678b11340080d11391ea54d890c11accc0dd06b2bd5f188335ef858cec8eef",
            proof["ops_archive_sha256"],
        )
        self.assertEqual(35, proof["ops_member_count"])
        self.assertEqual(0, proof["ops_active_workflows"])
        self.assertEqual(0, proof["ops_runtime_bytecode"])
        self.assertTrue(proof["owner_execution_evidence_intake_in_ops"])
        self.assertTrue(proof["owner_execution_evidence_contract_in_ops"])
        self.assertEqual(
            "57576b26f62eccb6ebafdbec070d872a764d64b47f352fb5cb44eb14f6e0e41f",
            proof["export_receipt_sha256"],
        )
        self.assertEqual(
            "a4795783b18a78a6e20a3e4eb31e1aa1321c35fb4f544f61ddbb1b78ff9b456d",
            proof["export_receipt_file_sha256"],
        )
        self.assertEqual(
            "f0f6bb7d4901817fcde7357846db12017521eda6810d74cdfcd91f2a1a862647",
            proof["freeze_receipt_sha256"],
        )
        self.assertEqual(
            "8fee80843f347f21141cd71162a62fa3d695fb3092d89d6e6cc9deba408e2bdd",
            proof["owner_packet_file_sha256"],
        )
        self.assertEqual(
            "7f74ae4454e477fa2607c639a06162a3c85bf89513f01ad918b368c34ebb6ea0",
            proof["owner_packet_sha256"],
        )
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        self.assertEqual(0, proof["unexpected_active_workflows"])

    def test_drive_release_readback_permissions_and_hash_are_exact(self):
        drive = load(RECEIPT)["drive_release"]
        self.assertEqual(
            "1el3MAchq7G7rzCHa5TLjg5Py1UoOoIOjgc4K0M0lwZU", drive["file_id"]
        )
        self.assertEqual(4341, drive["export_size"])
        self.assertEqual(
            "d474cb96a28fa85fb455c285d988b9ed14122e5707f9024f896e4de0acbb1b20",
            drive["export_sha256"],
        )
        self.assertEqual("2026-08-05T08:20:32.710Z", drive["modified_time"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual("VERIFIED", drive["readback"])

    def test_dependency_service_priority_authority_and_truth_remain_fail_closed(self):
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        receipt = load(RECEIPT)
        self.assertEqual(
            [f"C{i:02d}" for i in range(1, 16)], projection["dependency_order"]
        )
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        truth = receipt["commercial_truth"]
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["customer_demand"])
        self.assertEqual("NOT_PROVEN", truth["cloud_run_operation"])
        self.assertEqual(0, truth["verified_live_revenue_events"])
        self.assertFalse(truth["full_commercial_maturity"])
        attestation = receipt["attestation_truth"]
        self.assertFalse(attestation["owner_controlled_custody_proven"])
        self.assertFalse(attestation["owner_execution_present"])
        self.assertFalse(attestation["owner_authorization_present"])
        self.assertFalse(attestation["provider_authority_proven"])
        self.assertFalse(attestation["provider_apply_proven"])
        self.assertFalse(attestation["provider_native_outcome_proven"])
        checkpoint_truth = checkpoint["owner_execution_truth"]
        self.assertFalse(checkpoint_truth["owner_identity_authenticity_proven"])
        authority = receipt["provider_authority"]
        self.assertEqual(
            "SELECTED_REPOSITORY_ONLY",
            authority["installation_repository_scope_assessment"],
        )
        self.assertEqual(
            ["mosianekk-lang/Federation-Omega"],
            authority["installed_repositories"],
        )
        self.assertEqual(
            "NOT_FOUND_NOT_CLAIMED_CREATED", authority["target_core_repository"]
        )
        self.assertEqual(
            "NOT_FOUND_NOT_CLAIMED_CREATED", authority["target_ops_repository"]
        )
        self.assertFalse(authority["provider_mutation_performed"])


if __name__ == "__main__":
    unittest.main()
