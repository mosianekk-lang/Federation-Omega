from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "alpha_omega_commercial" / "phoenix_core_runtime_purity_checkpoint_v24.json"
PROJECTION = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v24.json"


def canonical_hash(payload: dict, field: str) -> str:
    body = dict(payload)
    body.pop(field, None)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class PhoenixCoreRuntimePurityCheckpointV24Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        cls.projection = json.loads(PROJECTION.read_text(encoding="utf-8"))

    def test_hash_bound_checkpoint_and_projection(self) -> None:
        self.assertEqual(
            self.checkpoint["checkpoint_sha256"],
            canonical_hash(self.checkpoint, "checkpoint_sha256"),
        )
        self.assertEqual(
            self.projection["projection_sha256"],
            canonical_hash(self.projection, "projection_sha256"),
        )

    def test_dependency_order_and_stage_path_are_preserved(self) -> None:
        self.assertEqual(
            [f"C{number:02d}" for number in range(1, 16)],
            self.projection["dependency_order"],
        )
        self.assertTrue(self.projection["dependency_order_preserved"])
        expected_path = ["C03", "C06", "C07", "C11", "C14", "C15"]
        self.assertEqual(expected_path, self.checkpoint["dependency_path"])
        self.assertEqual(expected_path, self.projection["advanced_internal_slice"]["stage_path"])
        self.assertTrue(self.projection["service_enabled_platform_first"])
        self.assertTrue(self.projection["self_service_saas_held"])

    def test_exact_provider_native_proof_is_bound(self) -> None:
        proof = self.checkpoint["provider_native_proof"]
        self.assertEqual("8e844204d906c5de7aee80a423aae8411f6e980a", proof["source_sha"])
        self.assertEqual(30947774350, proof["workflow_run"])
        self.assertEqual(92121940441, proof["workflow_job"])
        self.assertEqual("phoenix-freeze/verified", proof["commit_status"])
        self.assertEqual("success", proof["conclusion"])
        self.assertEqual(8907794843, proof["cutover_artifact"]["artifact_id"])
        self.assertEqual(
            "sha256:81495be2abab231cb6919e4d3750572da85ba926a85c870f1ed466490014b4e9",
            proof["cutover_artifact"]["artifact_digest"],
        )
        self.assertEqual(8907794516, proof["freeze_artifact"]["artifact_id"])
        self.assertEqual(
            "sha256:942f5f94885711c36c126b0d83948770f951eb6aba729a9e34703d9334f70beb",
            proof["freeze_artifact"]["artifact_digest"],
        )
        self.assertEqual("skipped_not_requested", proof["workflow_steps"]["pst_composite_verification"])

    def test_export_and_freeze_invariants_are_exact(self) -> None:
        receipt = self.checkpoint["export_receipt"]
        core = receipt["core"]
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertEqual("1.0.5", receipt["policy_version"])
        self.assertEqual(
            "67133229fa9bb09f95cd0c37ca4e8e9cf4e7e730a353a260f5febc7a13baad68",
            receipt["receipt_sha256"],
        )
        self.assertEqual(
            "e35a48d0ac6221120d68d42b9a2be687150af37d6e882032a0c714ba88663693",
            core["archive_sha256"],
        )
        self.assertEqual(0, core["workflow_count"])
        self.assertEqual(0, core["migration_control_test_count"])
        self.assertEqual(0, core["runtime_state_count"])
        self.assertEqual(0, core["secret_marker_count"])
        self.assertEqual(135, core["retained_test_count"])
        self.assertEqual("PASS", core["retained_test_result"])
        self.assertFalse(receipt["provider_apply_performed"])
        self.assertFalse(receipt["source_mutation_attempted"])
        self.assertFalse(receipt["credential_value_recorded"])

        freeze = self.checkpoint["execution_freeze_receipt"]
        self.assertEqual("VERIFIED", freeze["status"])
        self.assertEqual([], freeze["unexpected_active"])
        self.assertEqual([], freeze["missing_required"])
        self.assertFalse(freeze["source_mutation_attempted"])
        self.assertEqual(140, freeze["disabled_total_after"])

    def test_drive_release_is_private_and_hash_bound(self) -> None:
        drive = self.checkpoint["google_drive_release"]
        self.assertEqual("1qU5Ax4fWOsCm63qop2KngDKfT4Ja12GgNtSCQZUaV1Y", drive["file_id"])
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(4868, drive["text_export_size_bytes"])
        self.assertEqual(
            "e08efa036e9846302625165fac35fe1213972a47456dc43888dd05bdbfe08ce8",
            drive["text_export_sha256"],
        )

    def test_external_commercial_gates_are_not_overclaimed(self) -> None:
        truth = self.checkpoint["commercial_truth"]
        self.assertEqual("VERIFIED_AND_PRIORITISED", truth["service_enabled_platform"])
        self.assertEqual("HELD", truth["self_service_saas"])
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["customer_demand"])
        self.assertEqual("NOT_PROVEN", truth["signed_customer_contract"])
        self.assertEqual("PROVIDER_BLOCKED_NO_FRESH_AUTHORITY", truth["payment_provider_operation"])
        self.assertEqual("NOT_PROVEN", truth["cloud_run_operation"])
        self.assertEqual("UNVERIFIED", truth["enterprise_assurance"])
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["partner_adoption"])
        self.assertEqual("PRODUCTION_PROOF_REQUIRED", truth["production_scale"])
        self.assertEqual(0, truth["verified_live_revenue_events"])
        self.assertFalse(truth["full_commercial_maturity"])
        self.assertEqual(
            "PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED",
            self.projection["provider_execution_plane_cutover"],
        )

    def test_owner_and_institution_boundaries_are_preserved(self) -> None:
        owner = self.checkpoint["owner_authority"]
        for field in (
            "financial_commitments",
            "contracts",
            "external_communications",
            "consequential_releases",
        ):
            self.assertEqual("OWNER_RESERVED", owner[field])
        self.assertEqual(
            "OWNER_RESERVED_FRESH_EXACT_AUTHORIZATION_REQUIRED",
            owner["execution_plane_cutover"],
        )
        institution = self.checkpoint["institution_scope"]
        self.assertEqual(
            "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK",
            institution["P13"],
        )
        self.assertEqual(
            "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
            institution["P15"],
        )
        self.assertEqual("UNVERIFIED_SCOPE_HELD", institution["institution_v3_google_drive_publication"])


if __name__ == "__main__":
    unittest.main()
