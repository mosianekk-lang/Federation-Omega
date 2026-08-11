from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_attested_authorization_checkpoint_v36.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v36.json"
RECEIPT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_attested_authorization_release_receipt_v36.json"
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


class ProviderAttestedAuthorizationReleaseV36Tests(unittest.TestCase):
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
            "PROVIDER_ATTESTED_AUTHORIZATION_INTAKE_PROVIDER_PROOF_VERIFIED_"
            "OWNER_EXECUTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED",
            receipt["status"],
        )

    def test_provider_native_admission_and_current_main_proof_are_exact(self):
        receipt = load(RECEIPT)
        proof = receipt["provider_proof"]
        self.assertEqual(282, receipt["implementation_pr"])
        self.assertEqual(
            "ae55181f2947196fb195488c3347c19737af5323",
            receipt["implementation_pr_head"],
        )
        self.assertEqual(
            "4534469a2059f9233a3db432fefde1ad54893fc4",
            receipt["merged_main_sha"],
        )
        self.assertEqual(30984408799, proof["airlock_run"])
        self.assertEqual(92235783119, proof["airlock_job"])
        self.assertEqual(8921464481, proof["airlock_artifact_id"])
        self.assertEqual(
            "1b3fd1c43c8faa33ddf4055155e40503d117ab4879fd4ac3364465783edcdfa7",
            proof["airlock_artifact_sha256"],
        )
        self.assertEqual(
            "17bb4208b420d9a0683ad7c3f8bcaa12869879e79159f3db4c28025af4936c05",
            proof["source_provenance_receipt_sha256"],
        )
        self.assertEqual(0, proof["airlock_findings"])
        self.assertEqual(0, proof["changed_workflows"])
        self.assertEqual(0, proof["unadmitted_commits"])
        self.assertEqual(217, proof["provider_v3_family_tests_passed"])
        self.assertEqual(30984494856, proof["phoenix_run"])
        self.assertEqual(92236049483, proof["phoenix_job"])
        self.assertEqual(8921503682, proof["cutover_artifact_id"])
        self.assertEqual(
            "6b4848e768ef0d27da70894c2b6672f16b85d3c696ab9f65505945d691f14539",
            proof["cutover_artifact_sha256"],
        )
        self.assertEqual(8921503263, proof["execution_freeze_artifact_id"])
        self.assertEqual(
            "ba8fc7dc2a41bdcb8cbb3cc2ea827170e30bc69ea1c05d69d7c40965eaca7920",
            proof["execution_freeze_artifact_sha256"],
        )
        self.assertEqual(
            "d1e3791652261edebcb79320c27c879e262a95231b9f3911875d9b49f7bef2f8",
            proof["core_archive_sha256"],
        )
        self.assertEqual(
            "3535e696c05cb0ae09f3759276009bbd794e39149ebe85cbfe99343495f57074",
            proof["ops_archive_sha256"],
        )
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        self.assertEqual(0, proof["unexpected_active_workflows"])

    def test_drive_release_readback_and_permissions_are_exact(self):
        drive = load(RECEIPT)["drive_release"]
        self.assertEqual(
            "1sQ4AA4h0OSRJ_ZTV9d-28KAffkDL6cOhX6h7IDRxPZQ", drive["file_id"]
        )
        self.assertEqual(5583, drive["export_size"])
        self.assertEqual(
            "3aec95eaa58313d4522b32ffdd02c2275d723d05b236d86eaee73a535b268dcc",
            drive["export_sha256"],
        )
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual("VERIFIED", drive["readback"])

    def test_dependency_service_priority_and_truth_boundary_remain_fail_closed(self):
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
        self.assertFalse(
            projection["provider_execution_plane"]["provider_apply_performed"]
        )
        truth = receipt["commercial_truth"]
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["customer_demand"])
        self.assertEqual("NOT_PROVEN", truth["cloud_run_operation"])
        self.assertEqual(0, truth["verified_live_revenue_events"])
        self.assertFalse(truth["full_commercial_maturity"])
        attestation = checkpoint["attestation_truth"]
        self.assertFalse(attestation["owner_controlled_custody_proven"])
        self.assertFalse(attestation["owner_execution_present"])
        self.assertFalse(attestation["owner_attestation_present"])
        self.assertFalse(attestation["owner_identity_authenticity_proven"])
        self.assertFalse(attestation["provider_native_attestation_readback_present"])
        self.assertFalse(attestation["owner_authorization_present"])
        authority = receipt["provider_authority"]
        self.assertEqual(
            "SELECTED_REPOSITORY_ONLY",
            authority["installation_repository_scope_assessment"],
        )
        self.assertEqual(
            "NOT_FOUND_NOT_CLAIMED_CREATED", authority["target_core_repository"]
        )
        self.assertEqual(
            "NOT_FOUND_NOT_CLAIMED_CREATED", authority["target_ops_repository"]
        )


if __name__ == "__main__":
    unittest.main()
