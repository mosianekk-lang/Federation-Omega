from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_handoff_checkpoint_v37.json"
)
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v37.json"
RECEIPT = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_owner_execution_handoff_release_receipt_v37.json"
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


class OwnerExecutionHandoffReleaseV37Tests(unittest.TestCase):
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
            "OWNER_EXECUTION_HANDOFF_PROVIDER_PROOF_VERIFIED_"
            "OWNER_ACTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED",
            receipt["status"],
        )

    def test_provider_native_admission_and_current_main_proof_are_exact(self):
        receipt = load(RECEIPT)
        proof = receipt["provider_proof"]
        self.assertEqual(284, receipt["implementation_pr"])
        self.assertEqual(
            "f30b23ed79393d58b26c69a1efbd6dcc13ea3017",
            receipt["implementation_pr_head"],
        )
        self.assertEqual(
            "07370ef4466a6c20bc10e3274f7302b217ee56dd",
            receipt["merged_main_sha"],
        )
        self.assertEqual(30986061179, proof["airlock_run"])
        self.assertEqual(92240970669, proof["airlock_job"])
        self.assertEqual(8922110117, proof["airlock_artifact_id"])
        self.assertEqual(
            "74b738172de34b9f1ca9e44e04d644af8594d8263511ab0817b89900b6a51c15",
            proof["airlock_artifact_sha256"],
        )
        self.assertEqual(
            "9c8e1fbe332c395d6af76c91e7e239e50e9159144b89fe76ce36c1406eb5c340",
            proof["source_provenance_receipt_sha256"],
        )
        self.assertEqual(0, proof["airlock_findings"])
        self.assertEqual(0, proof["changed_workflows"])
        self.assertEqual(0, proof["unadmitted_commits"])
        self.assertEqual(223, proof["provider_v3_family_tests_passed"])
        self.assertEqual(30986173294, proof["phoenix_run"])
        self.assertEqual(92241317114, proof["phoenix_job"])
        self.assertEqual(8922153627, proof["cutover_artifact_id"])
        self.assertEqual(
            "c438aac8521ee694df684a990d926d2148f41cd98705cf6667e05aa1ce3022da",
            proof["cutover_artifact_sha256"],
        )
        self.assertEqual(8922153266, proof["execution_freeze_artifact_id"])
        self.assertEqual(
            "0280f79d4cbb669810aaaccf5af1ff46befe3101fc89181708c8285e951f7764",
            proof["execution_freeze_artifact_sha256"],
        )
        self.assertEqual(
            "336aa6c071833607c00189dc10a64edd251bf5e10517c0e7ae0ef32f8f38513d",
            proof["core_archive_sha256"],
        )
        self.assertEqual(
            "12c7de5c3bd32eec85b60cee6f3c4342e4ff76a644f3a1ec66ec6daf27e6a3dd",
            proof["ops_archive_sha256"],
        )
        self.assertEqual(
            "abedc496c6e150505248bb34dcf912079525dbf9b6a58932d36d834d230f32bc",
            proof["export_receipt_sha256"],
        )
        self.assertEqual(
            "83a63f23437e14366d6e3c2e537efc942f5300b538a48764e41b4fa29bea2475",
            proof["export_receipt_file_sha256"],
        )
        self.assertEqual(
            "356c08dea32241f7851b53d836abed1c38d5322e29e1986c451cf31605546cf8",
            proof["freeze_receipt_sha256"],
        )
        self.assertEqual(
            "18373575ea3fafea0aacabf985e588538bff5dfefc859d5c8faf232e0bafc80a",
            proof["owner_packet_file_sha256"],
        )
        self.assertEqual(
            "e0aea075ada1b70a4dee4ea9d94adaff31e2db0aa1925ab983ea460d7cb0f3de",
            proof["owner_packet_sha256"],
        )
        self.assertFalse(proof["provider_apply_performed"])
        self.assertFalse(proof["source_mutation_attempted"])
        self.assertEqual(0, proof["unexpected_active_workflows"])

    def test_drive_release_readback_and_permissions_are_exact(self):
        drive = load(RECEIPT)["drive_release"]
        self.assertEqual(
            "1Y7dn5q_t4aqvCzk8zSDZp-NvSp_GN-ucyHlCGnBLbDs", drive["file_id"]
        )
        self.assertEqual(5927, drive["export_size"])
        self.assertEqual(
            "6881957c7eb92954f4d4f7fb23010164b952c7b93e168f5a4ab8a0049c1dde06",
            drive["export_sha256"],
        )
        self.assertEqual("2026-08-05T07:47:55.049Z", drive["modified_time"])
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
        attestation = checkpoint["owner_execution_truth"]
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
        self.assertFalse(authority["provider_mutation_performed"])


if __name__ == "__main__":
    unittest.main()
