from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_authenticated_owner_attestation_checkpoint_v35.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v35.json"
RECEIPT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_provider_authenticated_owner_attestation_release_receipt_v35.json"
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


class ProviderAuthenticatedOwnerAttestationReleaseV35Tests(unittest.TestCase):
    def test_checkpoint_projection_and_receipt_are_hash_bound(self):
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        receipt = load(RECEIPT)
        verify_hash(checkpoint, "checkpoint_sha256")
        verify_hash(projection, "projection_sha256")
        verify_hash(receipt, "receipt_sha256")
        expected = (
            "PROVIDER_AUTHENTICATED_OWNER_ATTESTATION_READBACK_"
            "PROVIDER_PROOF_VERIFIED_OWNER_EXECUTION_AND_"
            "PROVIDER_NATIVE_ATTESTATION_REQUIRED"
        )
        self.assertEqual(expected, checkpoint["status"])
        self.assertEqual(expected, receipt["status"])
        self.assertIn("PROVIDER_PROOF_VERIFIED", projection["canonical_status"])
        self.assertEqual(
            checkpoint["checkpoint_sha256"], receipt["checkpoint_sha256"]
        )
        self.assertEqual(
            projection["projection_sha256"], receipt["projection_sha256"]
        )

    def test_provider_native_admission_and_current_main_proof_are_exact(self):
        proof = load(CHECKPOINT)["provider_proof"]
        self.assertEqual(280, proof["implementation_pr"])
        self.assertEqual(
            "21e450ad52583f9b2c6f68831612bb520d10fe86",
            proof["implementation_pr_head"],
        )
        self.assertEqual(30982229949, proof["airlock_run"])
        self.assertEqual(92228934162, proof["airlock_job"])
        self.assertEqual(8920585849, proof["airlock_artifact_id"])
        self.assertEqual(
            "dcd27447926929b8a3784246f6973cd5a330861fab3deeeef5f5d2aee13ce6f2",
            proof["airlock_artifact_sha256"],
        )
        self.assertEqual(
            "9113edd6bbfd0068d5ffe6b3ef21571680cfd3d335c399a5fbb893d361d1f591",
            proof["source_provenance_receipt_sha256"],
        )
        self.assertEqual(0, proof["airlock_findings"])
        self.assertEqual(0, proof["changed_workflows"])
        self.assertEqual(0, proof["unadmitted_commits"])
        self.assertEqual(207, proof["provider_v3_family_tests_passed"])
        self.assertEqual("SUCCESS", proof["public_repository_leak_guard"])
        self.assertEqual(
            "80cffe50c6cd5cc72604254c6882d2af5a97fdf5",
            proof["merged_main_sha"],
        )
        self.assertEqual(30982388563, proof["phoenix_run"])
        self.assertEqual(92229410375, proof["phoenix_job"])
        self.assertEqual(8920643963, proof["cutover_artifact_id"])
        self.assertEqual(
            "68a1e2943a819e71656ac385b5bac2fe8e804a515ce2bf192a7444d79ecea535",
            proof["cutover_artifact_sha256"],
        )
        self.assertEqual(8920643607, proof["execution_freeze_artifact_id"])
        self.assertEqual(
            "ced880d2455a299e37364bde1b9609630e156f8d12ae1e6e13c1f9df07d1864f",
            proof["execution_freeze_artifact_sha256"],
        )
        self.assertEqual(0, proof["core_active_workflows"])
        self.assertEqual(0, proof["ops_active_workflows"])
        self.assertEqual(0, proof["runtime_bytecode"])
        self.assertTrue(proof["ops_provider_attestation_engine_included"])
        self.assertTrue(proof["ops_provider_attestation_contract_included"])
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        self.assertEqual(0, proof["unexpected_active_workflows"])

    def test_drive_release_readback_and_permissions_are_exact(self):
        drive = load(CHECKPOINT)["drive_release"]
        self.assertEqual(
            "1Q0gZqhMVVtxEfGMTlHnI90Rkdq2NSkdYHWqaXkhcjy4", drive["file_id"]
        )
        self.assertEqual(5063, drive["export_size"])
        self.assertEqual(
            "ce3461cb79dd637e46374bed6d7ed301f93c072b27d8433691c5cd278546aa7e",
            drive["export_sha256"],
        )
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual("VERIFIED", drive["readback"])

    def test_dependency_service_priority_and_truth_boundary_remain_fail_closed(self):
        checkpoint = load(CHECKPOINT)
        projection = load(PROJECTION)
        self.assertEqual(
            [f"C{i:02d}" for i in range(1, 16)], projection["dependency_order"]
        )
        self.assertTrue(projection["dependency_order_preserved"])
        self.assertTrue(projection["service_enabled_platform_first"])
        self.assertTrue(projection["self_service_saas_held"])
        self.assertEqual(0, projection["verified_live_revenue_events"])
        self.assertFalse(projection["full_commercial_maturity"])
        self.assertIn(
            "PROVIDER_BLOCKED",
            projection["provider_execution_plane"]["private_github_route"],
        )
        self.assertFalse(
            projection["provider_execution_plane"]["provider_apply_performed"]
        )
        truth = checkpoint["commercial_truth"]
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
        authority = checkpoint["provider_authority_readback"]
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
