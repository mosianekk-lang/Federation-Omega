from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_step2_custody_packet_checkpoint_v40.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v40.json"
RECEIPT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_step2_custody_packet_release_receipt_v40.json"
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


class OwnerExecutionStep2CustodyPacketReleaseV40Tests(unittest.TestCase):
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
            "OWNER_EXECUTION_STEP2_CUSTODY_PACKET_PROVIDER_PROOF_VERIFIED_"
            "OWNER_EXECUTION_REQUIRED",
            receipt["status"],
        )

    def test_provider_native_admission_current_main_and_export_are_exact(self):
        receipt = load(RECEIPT)
        proof = receipt["provider_proof"]
        self.assertEqual(290, receipt["implementation_pr"])
        self.assertEqual(
            "b948c10ecd658b4b8dfe94b7328d3d82c11c70fc",
            receipt["implementation_pr_head"],
        )
        self.assertEqual(
            "560a59e9ac8f120768c89e2e823994b3194dcd3f",
            receipt["merged_main_sha"],
        )
        self.assertEqual(30993677097, proof["airlock_run"])
        self.assertEqual(92265507940, proof["airlock_job"])
        self.assertEqual(8925196161, proof["airlock_artifact_id"])
        self.assertEqual(
            "cf02ff9503a0be64d10e86cb190bc89bf00a2a4d473a41d4038039af0bf70540",
            proof["airlock_artifact_sha256"],
        )
        self.assertEqual(
            "7dbfe8fd23d172ef7777ec10d3d91c5036262c2fe44415d4522bc7ee6b1ba385",
            proof["source_provenance_receipt_sha256"],
        )
        self.assertEqual(0, proof["airlock_findings"])
        self.assertEqual(0, proof["changed_workflows"])
        self.assertEqual(0, proof["unadmitted_commits"])
        self.assertEqual(261, proof["provider_v3_family_tests_passed"])
        self.assertEqual(30993745021, proof["phoenix_run"])
        self.assertEqual(92265728432, proof["phoenix_job"])
        self.assertEqual(8925229704, proof["cutover_artifact_id"])
        self.assertEqual(
            "44554d521a95d20bac4ce51a1cf6273b3e5269e4e33f52747ffa0732361b7881",
            proof["cutover_artifact_sha256"],
        )
        self.assertEqual(8925228847, proof["execution_freeze_artifact_id"])
        self.assertEqual(
            "34289fd9c8d8cfe6f96115b89c91d68ea607961a24d05b7167669516443457cf",
            proof["execution_freeze_artifact_sha256"],
        )
        self.assertEqual(
            "bb69634394c0a9bd8e1803107a268e7c10b577f0d17d342e5b7a702de0ad8faf",
            proof["core_archive_sha256"],
        )
        self.assertEqual(1192, proof["core_member_count"])
        self.assertEqual(0, proof["core_active_workflows"])
        self.assertEqual(0, proof["core_runtime_bytecode"])
        self.assertEqual(
            "35759d0866985b6662f2a82db697bbae2ba0422cf28a3c4747177ea59a14878e",
            proof["ops_archive_sha256"],
        )
        self.assertEqual(39, proof["ops_member_count"])
        self.assertEqual(0, proof["ops_active_workflows"])
        self.assertEqual(0, proof["ops_runtime_bytecode"])
        self.assertTrue(proof["owner_execution_step2_custody_packet_in_ops"])
        self.assertTrue(
            proof["owner_execution_step2_custody_packet_contract_in_ops"]
        )
        self.assertEqual(
            "23491ffce579f12c3f366e5e016625ee77631fa3cb985d740dbf33e315dfc7a0",
            proof["export_receipt_sha256"],
        )
        self.assertEqual(
            "d4797d765302716efa4ba8f99853a3c5c92154895f42b2b522b20551f0005228",
            proof["export_receipt_file_sha256"],
        )
        self.assertEqual(
            "dd23b93e708d177d0cdac453bf73bf139b223f554fd6d8673c5695ed788785f7",
            proof["freeze_receipt_sha256"],
        )
        self.assertEqual(
            "c0dc02d4a7f86d3e94fc2e3ea191052a630c5cc4d132221cc7e054479a980491",
            proof["owner_packet_file_sha256"],
        )
        self.assertEqual(
            "78363b970ad2d2f10dd8ea030ad13758cab1f9c62189ba01eca13962f74735fc",
            proof["owner_packet_sha256"],
        )
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        self.assertEqual(0, proof["unexpected_active_workflows"])

    def test_drive_release_readback_permissions_and_hash_are_exact(self):
        drive = load(RECEIPT)["drive_release"]
        self.assertEqual(
            "1nTzPpE5vJoKyQ8VV8H-GcBF9K7nFbV3TRFEKtwCrhYo", drive["file_id"]
        )
        self.assertEqual(5474, drive["export_size"])
        self.assertEqual(
            "b1b838af061014ac39415451997f55a9d297e75de259a7c97241c0d339f53484",
            drive["export_sha256"],
        )
        self.assertEqual("2026-08-05T09:37:46.296Z", drive["modified_time"])
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
        self.assertEqual(
            "PROVIDER_PROOF_VERIFIED_OWNER_EXECUTION_REQUIRED",
            projection["advanced_internal_slice"][
                "step2_custody_execution_packet"
            ],
        )
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
