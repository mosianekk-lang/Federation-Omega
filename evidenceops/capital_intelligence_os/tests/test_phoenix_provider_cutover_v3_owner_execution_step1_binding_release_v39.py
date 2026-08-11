from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_step1_binding_checkpoint_v39.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v39.json"
RECEIPT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_step1_binding_release_receipt_v39.json"
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


class OwnerExecutionStep1BindingReleaseV39Tests(unittest.TestCase):
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
            "OWNER_EXECUTION_STEP1_BINDING_PROVIDER_PROOF_VERIFIED_"
            "OWNER_CUSTODY_ACTION_REQUIRED",
            receipt["status"],
        )

    def test_provider_native_admission_current_main_and_export_are_exact(self):
        receipt = load(RECEIPT)
        proof = receipt["provider_proof"]
        self.assertEqual(288, receipt["implementation_pr"])
        self.assertEqual(
            "1f18a1ec7ed9d92e6bfe1d867cfb99b7cb97ad63",
            receipt["implementation_pr_head"],
        )
        self.assertEqual(
            "7cd6caccb8e83ca2420252efd960c0a1ad2fe087",
            receipt["merged_main_sha"],
        )
        self.assertEqual(30990265169, proof["airlock_run"])
        self.assertEqual(92254461121, proof["airlock_job"])
        self.assertEqual(8923784059, proof["airlock_artifact_id"])
        self.assertEqual(
            "167c9cb364ed33c84f7ea388f26bd7d15bf5c858f5701aa99f68037a59697158",
            proof["airlock_artifact_sha256"],
        )
        self.assertEqual(
            "24018df305cfe05c41673c9259be728808fcaf20521bb6ec774a26027675558a",
            proof["source_provenance_receipt_sha256"],
        )
        self.assertEqual(0, proof["airlock_findings"])
        self.assertEqual(0, proof["changed_workflows"])
        self.assertEqual(0, proof["unadmitted_commits"])
        self.assertEqual(249, proof["provider_v3_family_tests_passed"])
        self.assertEqual(30990382791, proof["phoenix_run"])
        self.assertEqual(92254838951, proof["phoenix_job"])
        self.assertEqual(8923831855, proof["cutover_artifact_id"])
        self.assertEqual(
            "cca3deb00013b821d32c8ff5c1c282b263ec38bace0db7d1a016361d4b711b61",
            proof["cutover_artifact_sha256"],
        )
        self.assertEqual(8923830943, proof["execution_freeze_artifact_id"])
        self.assertEqual(
            "94866b8a744426f40a6ed08f4b02b06dac142c7ed5e75abf3fec850b0c9a9ae1",
            proof["execution_freeze_artifact_sha256"],
        )
        self.assertEqual(
            "bf2667a9d79f7799bda48278b50dff40fa5397407ea183e1f67d1dd44ce8b831",
            proof["core_archive_sha256"],
        )
        self.assertEqual(1188, proof["core_member_count"])
        self.assertEqual(0, proof["core_active_workflows"])
        self.assertEqual(0, proof["core_runtime_bytecode"])
        self.assertEqual(
            "5b0706c4c76cf7470c304eb2fb97fb19377359d2e9d13808e186994ff21e9c21",
            proof["ops_archive_sha256"],
        )
        self.assertEqual(37, proof["ops_member_count"])
        self.assertEqual(0, proof["ops_active_workflows"])
        self.assertEqual(0, proof["ops_runtime_bytecode"])
        self.assertTrue(proof["owner_execution_step1_binding_in_ops"])
        self.assertTrue(proof["owner_execution_step1_binding_contract_in_ops"])
        self.assertEqual(
            "dde8613c6cf4e961a0158da36f5c6da75b8517b1563fc5f3b03ab17b13ca7617",
            proof["export_receipt_sha256"],
        )
        self.assertEqual(
            "e7a7512e9c68167e8eb59174a667d19c245a382d2f4f2aebc079c901cd8f3d40",
            proof["export_receipt_file_sha256"],
        )
        self.assertEqual(
            "45286859d7d7e61b29f6ee20735d3b6f5c820298ebdec30da5cf748fdc384937",
            proof["freeze_receipt_sha256"],
        )
        self.assertEqual(
            "be2b8ba721f5597c6b5d43e39b152544cee4a3bf2001d29cb3926c3c83b6ff39",
            proof["owner_packet_file_sha256"],
        )
        self.assertEqual(
            "b824a4c3e180bdf4a48b241e696e04eff0ae6a3cd02f457ff3f4e9894beac640",
            proof["owner_packet_sha256"],
        )
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        self.assertEqual(0, proof["unexpected_active_workflows"])

    def test_drive_release_readback_permissions_and_hash_are_exact(self):
        drive = load(RECEIPT)["drive_release"]
        self.assertEqual(
            "1587exZVH7QeiJ7qLx_dG4gZnJhdOxzo6Cca4xTjs2hY", drive["file_id"]
        )
        self.assertEqual(5219, drive["export_size"])
        self.assertEqual(
            "15fb691dde7a15cd2e9c0e43cb9c80096303d8faf40d2da50c7ed27695fc2a2f",
            drive["export_sha256"],
        )
        self.assertEqual("2026-08-05T08:49:18.105Z", drive["modified_time"])
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
            "PROVIDER_PROOF_VERIFIED",
            projection["advanced_internal_slice"]["step1_packet_release_binding"],
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
