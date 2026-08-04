from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_authorized_execution_checkpoint_v25.json"
)
PROJECTION_PATH = (
    ROOT
    / "alpha_omega_commercial"
    / "programme_maturity_effective_v25.json"
)


def canonical_sha256(payload: dict, field: str) -> str:
    body = dict(payload)
    body.pop(field)
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class PhoenixAuthorizedExecutionCheckpointV25Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        cls.projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))

    def test_checkpoint_and_projection_are_hash_bound(self):
        self.assertEqual(
            self.checkpoint["checkpoint_sha256"],
            canonical_sha256(self.checkpoint, "checkpoint_sha256"),
        )
        self.assertEqual(
            self.projection["projection_sha256"],
            canonical_sha256(self.projection, "projection_sha256"),
        )

    def test_dependency_order_and_service_platform_priority_are_preserved(self):
        self.assertEqual(
            ["C03", "C06", "C07", "C11", "C14", "C15"],
            self.checkpoint["dependency_path"],
        )
        self.assertEqual(
            [f"C{i:02d}" for i in range(1, 16)],
            self.projection["dependency_order"],
        )
        self.assertTrue(self.projection["dependency_order_preserved"])
        self.assertTrue(self.projection["service_enabled_platform_first"])
        self.assertTrue(self.projection["self_service_saas_held"])

    def test_exact_provider_native_final_head_proof_is_bound(self):
        proof = self.checkpoint["provider_native_final_head"]
        self.assertEqual(
            "3a715d0ac00501c045b856569c81242fdc05bca6",
            proof["source_sha"],
        )
        self.assertEqual(30949262846, proof["workflow_run"])
        self.assertEqual(92126950928, proof["workflow_job"])
        self.assertEqual("success", proof["conclusion"])
        self.assertEqual("phoenix-freeze/verified", proof["commit_status"])
        self.assertEqual(
            "sha256:1fef9271987dab8b2c4c925d201a87cb0deff3ebcab73f4cadb926e2cf37e366",
            proof["cutover_artifact"]["artifact_digest"],
        )
        self.assertEqual(
            "sha256:12a1d3214b402abfbb6f39742211474ba3055b2aa7d23091f4a075d9033fed1d",
            proof["freeze_artifact"]["artifact_digest"],
        )
        self.assertTrue(
            all(
                value == "success"
                for key, value in proof["workflow_steps"].items()
                if key != "pst_composite_verification"
            )
        )

    def test_authorized_execution_package_and_unknown_outcome_controls_are_verified(self):
        receipt = self.checkpoint["export_receipt"]
        engine = receipt["provider_cutover_engine"]
        self.assertEqual("3.2", engine["version"])
        self.assertEqual("V22", engine["authorization_execution_gate"])
        self.assertTrue(engine["authorization_decision_required"])
        self.assertTrue(engine["one_time_authorization_consumption_required"])
        self.assertFalse(engine["unknown_outcome_automatic_retry"])
        self.assertFalse(engine["provider_apply_performed"])
        self.assertFalse(engine["credential_value_recorded"])
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
        for path in (
            "phoenix/provider_cutover_authorized_executor.py",
            "phoenix/provider_cutover_authorization_use.py",
            "phoenix/provider_cutover_v3_1.py",
            "phoenix/provider_cutover_v3.py",
            "tests/test_phoenix_provider_cutover_v3_authorized_executor.py",
        ):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_airlock_repair_proof_and_direct_write_truth_are_not_diluted(self):
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

    def test_export_and_drive_evidence_are_exact_and_private(self):
        receipt = self.checkpoint["export_receipt"]
        self.assertEqual(
            "5141dbfaad0e0d059ff1aa8dc9d7919f0a9008f90afad0b02dd988014510e368",
            receipt["core"]["archive_sha256"],
        )
        self.assertEqual(
            "72184d5235e09019017af49314239c950de12853e133f36017d8f6113b6166b0",
            receipt["ops"]["archive_sha256"],
        )
        self.assertEqual(
            "01e59233b647ed907b70d3254946ca49fc67fed071fc9e44275f400b7c8f936f",
            receipt["receipt_sha256"],
        )
        self.assertEqual(135, receipt["core"]["retained_test_count"])
        self.assertEqual("PASS", receipt["core"]["retained_test_result"])
        drive = self.checkpoint["google_drive_release"]
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(4562, drive["text_export_size_bytes"])
        self.assertEqual(
            "4dce6469d1c4e8297ed1adfcaa9b885f28122e8b719e88f12d10c1aa66c61aa7",
            drive["text_export_sha256"],
        )

    def test_external_commercial_gates_and_owner_authority_remain_fail_closed(self):
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
        self.assertTrue(
            all(value.startswith("OWNER_RESERVED") for value in self.projection["owner_authority"].values())
        )

    def test_institution_scope_is_preserved_without_provider_writeback(self):
        scope = self.projection["institution_scope"]
        self.assertEqual(
            "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK",
            scope["P13"],
        )
        self.assertEqual(
            "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
            scope["P15"],
        )


if __name__ == "__main__":
    unittest.main()
