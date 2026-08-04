from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMERCIAL = ROOT / "alpha_omega_commercial"
CHECKPOINT = COMMERCIAL / "phoenix_authorized_execution_checkpoint_v25.json"
PROJECTION = COMMERCIAL / "programme_maturity_effective_v25.json"


def canonical_sha256(payload: dict, field: str) -> str:
    body = dict(payload)
    body.pop(field)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class PhoenixAuthorizedExecutionCheckpointV25Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        cls.projection = json.loads(PROJECTION.read_text(encoding="utf-8"))

    def test_checkpoint_and_projection_are_hash_bound(self) -> None:
        self.assertEqual(
            self.checkpoint["checkpoint_sha256"],
            canonical_sha256(self.checkpoint, "checkpoint_sha256"),
        )
        self.assertEqual(
            self.projection["projection_sha256"],
            canonical_sha256(self.projection, "projection_sha256"),
        )

    def test_dependency_order_and_service_first_policy_are_preserved(self) -> None:
        self.assertEqual(
            ["C03", "C06", "C07", "C11", "C14", "C15"],
            self.checkpoint["dependency_path"],
        )
        self.assertEqual(
            [f"C{stage:02d}" for stage in range(1, 16)],
            self.projection["dependency_order"],
        )
        self.assertTrue(self.projection["dependency_order_preserved"])
        self.assertTrue(self.projection["service_enabled_platform_first"])
        self.assertTrue(self.projection["self_service_saas_held"])

    def test_provider_native_final_head_and_artifacts_are_exact(self) -> None:
        proof = self.checkpoint["provider_native_final_head"]
        self.assertEqual(
            "3d08384ccc2a727f47013a21b0c16545f985f8ab", proof["source_sha"]
        )
        self.assertEqual(30949598671, proof["workflow_run"])
        self.assertEqual(92128076000, proof["workflow_job"])
        self.assertEqual("success", proof["conclusion"])
        self.assertEqual("phoenix-freeze/verified", proof["commit_status"])
        self.assertEqual(
            "sha256:60cc36066a82ee4f68c0414e5f9021ad6852133e5efede4e2ead3dc7f0d15848",
            proof["cutover_artifact"]["artifact_digest"],
        )
        self.assertEqual(
            "sha256:610ffa44405210d8960219afe47318a7df9c43931efbe40fcfc3d00fd8971e1b",
            proof["freeze_artifact"]["artifact_digest"],
        )

    def test_export_receipt_and_authorized_ops_package_are_exact(self) -> None:
        receipt = self.checkpoint["export_receipt"]
        self.assertEqual(
            "4783a29388ee93b3f6a0e6883a3e6c16f2fdb8939f8d74693c3b7de1c9d6fc26",
            receipt["core"]["archive_sha256"],
        )
        self.assertEqual(
            "86b59f255bbfe2407ff4d20c1c5644918cc6215987726b16dbabbffd356eb2b9",
            receipt["ops"]["archive_sha256"],
        )
        self.assertEqual(
            "5526930ccd05af6ae258d499d01609f8f6a1b287772f98111bea668146c8734a",
            receipt["receipt_sha256"],
        )
        self.assertEqual(135, receipt["core"]["retained_test_count"])
        self.assertEqual("PASS", receipt["core"]["retained_test_result"])
        self.assertEqual(0, receipt["ops"]["active_workflow_count"])
        self.assertEqual(
            {
                "provider_cutover.py",
                "provider_cutover_authorization_use.py",
                "provider_cutover_v3_1.py",
                "provider_cutover_v3_base.py",
            },
            set(receipt["ops"]["required_authorized_execution_files"]),
        )
        engine = receipt["provider_cutover_engine"]
        self.assertEqual("3.2", engine["version"])
        self.assertEqual("V22", engine["authorization_execution_gate"])
        self.assertTrue(engine["authorization_decision_required"])
        self.assertTrue(engine["one_time_authorization_consumption_required"])
        self.assertFalse(engine["unknown_outcome_automatic_retry"])
        self.assertFalse(engine["provider_apply_performed"])
        self.assertFalse(engine["credential_value_recorded"])

    def test_execution_code_and_regression_surface_are_present(self) -> None:
        required = (
            "phoenix/provider_cutover_authorized_executor.py",
            "phoenix/provider_cutover_authorization_use.py",
            "phoenix/provider_cutover_v3_1.py",
            "phoenix/provider_cutover_v3.py",
            "tests/test_phoenix_provider_cutover_v3_authorized_executor.py",
        )
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_repair_provenance_is_truthful_and_airlock_verified(self) -> None:
        lineage = self.checkpoint["implementation_lineage"]
        admission = self.checkpoint["provider_native_admission"]
        self.assertEqual(225, lineage["repair_pull_request"])
        self.assertEqual(
            "DIRECT_MAIN_WRITES_DETECTED_AND_REPAIRED_NO_RETROACTIVE_AIRLOCK_ADMISSION_CLAIMED",
            lineage["source_provenance_truth"],
        )
        self.assertEqual("PASS", admission["airlock_status"])
        self.assertEqual([], admission["airlock_findings"])
        self.assertEqual(0, admission["unadmitted_commit_count_for_repair_pr"])
        self.assertEqual(11, admission["provider_control_regressions"]["authorized_executor_tests"])
        self.assertEqual("PASS", admission["provider_control_regressions"]["v3_family_result"])
        self.assertEqual("SUCCESS", admission["public_repository_leak_guard"])

    def test_private_drive_release_and_external_gates_remain_fail_closed(self) -> None:
        drive = self.checkpoint["google_drive_release"]
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(4696, drive["text_export_size_bytes"])
        self.assertEqual(
            "9a7bc9399cd4724e0fb188a2836ed6674a08ecc53b8ba5da1ca382ccf3174317",
            drive["text_export_sha256"],
        )

        truth = self.checkpoint["commercial_truth"]
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["customer_demand"])
        self.assertEqual("NOT_PROVEN", truth["signed_customer_contract"])
        self.assertEqual(
            "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            truth["payment_provider_operation"],
        )
        self.assertEqual("NOT_PROVEN", truth["cloud_run_operation"])
        self.assertEqual("UNVERIFIED", truth["enterprise_assurance"])
        self.assertEqual("MARKET_PROOF_REQUIRED", truth["partner_adoption"])
        self.assertEqual("PRODUCTION_PROOF_REQUIRED", truth["production_scale"])
        self.assertEqual(0, truth["verified_live_revenue_events"])
        self.assertFalse(truth["full_commercial_maturity"])
        self.assertFalse(
            self.checkpoint["operational_proof_gate"]["provider_apply_performed"]
        )
        self.assertFalse(
            self.checkpoint["operational_proof_gate"]["external_repository_created"]
        )
        self.assertEqual(
            "PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED",
            self.projection["provider_execution_plane_cutover"],
        )

    def test_institution_scope_and_owner_authority_are_preserved(self) -> None:
        scope = self.projection["institution_scope"]
        self.assertEqual(
            "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK",
            scope["P13"],
        )
        self.assertEqual(
            "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
            scope["P15"],
        )
        self.assertTrue(
            all(
                value.startswith("OWNER_RESERVED")
                for value in self.projection["owner_authority"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
