from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = (
    ROOT
    / "alpha_omega_commercial"
    / "phoenix_read_only_outcome_reconciliation_checkpoint_v26.json"
)
PROJECTION_PATH = (
    ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v26.json"
)


class PhoenixReadOnlyOutcomeReconciliationCheckpointV26Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        cls.projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def canonical_hash(payload: dict, hash_field: str) -> str:
        body = dict(payload)
        claimed = body.pop(hash_field)
        calculated = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if claimed != calculated:
            raise AssertionError(
                f"{hash_field} mismatch: claimed {claimed}, calculated {calculated}"
            )
        return claimed

    def test_checkpoint_and_projection_are_hash_bound(self):
        self.assertEqual(
            "f8b7019885ae59f531b79e6f83d6ade78555b67409254280c3c5749e3c9f1e67",
            self.canonical_hash(self.checkpoint, "checkpoint_sha256"),
        )
        self.assertEqual(
            "e328ab5a04b85da5c38eb67e288b41751bf836e0b0b0008f182e25d48cad7ada",
            self.canonical_hash(self.projection, "projection_sha256"),
        )

    def test_dependency_order_and_service_first_policy_are_preserved(self):
        self.assertEqual(
            [f"C{number:02d}" for number in range(1, 16)],
            self.projection["dependency_order"],
        )
        self.assertTrue(self.projection["dependency_order_preserved"])
        self.assertTrue(self.projection["service_enabled_platform_first"])
        self.assertTrue(self.projection["self_service_saas_held"])
        self.assertEqual(
            ["C03", "C06", "C07", "C11", "C14", "C15"],
            self.checkpoint["dependency_path"],
        )
        self.assertEqual(
            self.checkpoint["dependency_path"],
            self.projection["advanced_internal_slice"]["stage_path"],
        )

    def test_predecessor_and_implementation_lineage_are_exact(self):
        predecessor = self.checkpoint["predecessor"]
        self.assertEqual(
            "alpha_omega_commercial/phoenix_authorized_execution_checkpoint_v25.json",
            predecessor["checkpoint_file"],
        )
        self.assertEqual(
            "5a534f37b16c2d0f5eee614d9a5b3a5bd1d677cfca79478c7f90ebb36de28410",
            predecessor["checkpoint_sha256"],
        )
        self.assertEqual(
            "27913b8e4666a0208fca6d5d317e1470e9ad18b2b055fc9bce38bd9dc456463f",
            predecessor["programme_projection_sha256"],
        )
        lineage = self.checkpoint["implementation_lineage"]
        self.assertEqual(232, lineage["implementation_pull_request"])
        self.assertEqual(
            "c6354d9379dd0abc1f2d0035dec27e21fde6da93",
            lineage["implementation_merge_commit"],
        )
        self.assertEqual(0, lineage["workflow_change_count"])
        self.assertEqual(
            "PR_ASSOCIATED_HEAD_VERIFIED_ZERO_UNADMITTED_COMMITS",
            lineage["source_provenance_truth"],
        )

    def test_provider_native_admission_and_current_main_proof_are_exact(self):
        admission = self.checkpoint["provider_native_admission"]
        self.assertEqual(30956205046, admission["airlock_run"])
        self.assertEqual(92149720882, admission["airlock_job"])
        self.assertEqual(8911112188, admission["airlock_artifact_id"])
        self.assertEqual(
            "sha256:3a18c8d27cc6a431052edf88c581c65784742477a2178d5ad254b6057db5970a",
            admission["airlock_artifact_digest"],
        )
        self.assertEqual([], admission["airlock_findings"])
        self.assertEqual(0, admission["unadmitted_commit_count"])
        self.assertEqual("SUCCESS", admission["public_repository_leak_guard"])
        regressions = admission["provider_control_regressions"]
        self.assertEqual("74/74_PASS", regressions["provider_cutover_v3_family"])
        self.assertEqual(
            "9/9_PASS", regressions["read_only_outcome_reconciliation"]
        )
        self.assertEqual("6/6_PASS", regressions["phoenix_export_purity"])

        final_head = self.checkpoint["provider_native_final_head"]
        self.assertEqual(
            "c6354d9379dd0abc1f2d0035dec27e21fde6da93",
            final_head["source_sha"],
        )
        self.assertEqual(30956275861, final_head["workflow_run"])
        self.assertEqual(92149950357, final_head["workflow_job"])
        self.assertEqual("success", final_head["conclusion"])
        self.assertEqual("phoenix-freeze/verified", final_head["commit_status"])
        self.assertEqual(8911138573, final_head["cutover_artifact"]["artifact_id"])
        self.assertEqual(8911138304, final_head["freeze_artifact"]["artifact_id"])
        self.assertTrue(
            all(
                result == "success" or result == "skipped_not_requested"
                for result in final_head["workflow_steps"].values()
            )
        )

    def test_export_receipt_and_private_ops_recovery_package_are_exact(self):
        receipt = self.checkpoint["export_receipt"]
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertEqual("1.0.8", receipt["policy_version"])
        self.assertEqual(
            "d9e27d20a0cd3a012e3a81f1c7ffce1e85a328b9de42a3738b8c6747a998b3f9",
            receipt["receipt_sha256"],
        )
        self.assertEqual(
            "c8d533526cea1746ee8ac85401238a8ab02cb35c3c511486a5e568cdf85a564e",
            receipt["core"]["archive_sha256"],
        )
        self.assertEqual(
            "83f4e0c34f93253e933db369e4298cbe008011e9a8e281948b5841fd62031a7e",
            receipt["ops"]["archive_sha256"],
        )
        self.assertEqual(0, receipt["ops"]["active_workflow_count"])
        required = set(receipt["ops"]["required_execution_files"])
        self.assertIn("provider_cutover_outcome_reconciler.py", required)
        self.assertIn("provider_cutover_guarded.py", required)
        self.assertIn("provider_cutover_v3_live_guard.py", required)

        engine = receipt["provider_cutover_engine"]
        self.assertEqual("3.3", engine["version"])
        self.assertTrue(engine["read_only_outcome_reconciliation"])
        self.assertFalse(engine["outcome_reconciliation_mutation_allowed"])
        self.assertFalse(engine["provider_apply_performed"])
        self.assertFalse(engine["unknown_outcome_automatic_retry"])
        self.assertFalse(receipt["source_mutation_attempted"])

    def test_operational_gate_is_truthful_and_live_provider_write_is_not_claimed(self):
        gate = self.checkpoint["operational_proof_gate"]
        self.assertEqual("VERIFIED_GET_ONLY", gate["read_only_provider_client_surface"])
        self.assertEqual("VERIFIED", gate["safe_archive_inventory"])
        self.assertEqual(
            "VERIFIED_MOCK_PROVIDER_CONFORMANCE",
            gate["exact_provider_tree_path_size_mode_blob_binding"],
        )
        self.assertEqual(
            "NOT_PERFORMED_TARGET_REPOSITORIES_ABSENT",
            gate["live_target_provider_reconciliation"],
        )
        self.assertFalse(gate["external_repository_created"])
        self.assertFalse(gate["provider_apply_replayed"])
        self.assertFalse(gate["provider_mutation_performed"])
        self.assertEqual(
            "DISABLED_VERIFIED", gate["unknown_provider_outcome_automatic_retry"]
        )

    def test_private_drive_release_and_external_commercial_gates_remain_fail_closed(self):
        drive = self.checkpoint["google_drive_release"]
        self.assertEqual(
            "1iJVeR8B8t_RGOVZUCHzJPLcmnfTlwEPwx3l2Om3wXvQ", drive["file_id"]
        )
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(6053, drive["text_export_size_bytes"])
        self.assertEqual(
            "c3bc73ee8f0974e22baf88bfec310379115c23f5a7f72048f6f050565e98e07a",
            drive["text_export_sha256"],
        )

        truth = self.checkpoint["commercial_truth"]
        self.assertEqual("VERIFIED_AND_PRIORITISED", truth["service_enabled_platform"])
        self.assertEqual("HELD", truth["self_service_saas"])
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

    def test_owner_authority_institution_scope_and_release_projection_are_preserved(self):
        expected_owner = {
            "consequential_releases": "OWNER_RESERVED",
            "contracts": "OWNER_RESERVED",
            "execution_plane_cutover": "OWNER_RESERVED_FRESH_EXACT_AUTHORIZATION_REQUIRED",
            "external_communications": "OWNER_RESERVED",
            "financial_commitments": "OWNER_RESERVED",
            "revenue_recognition": "OWNER_RESERVED_PROVIDER_RECEIPT_REQUIRED",
        }
        self.assertEqual(expected_owner, self.checkpoint["owner_authority"])
        self.assertEqual(
            "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK",
            self.checkpoint["institution_scope"]["P13"],
        )
        self.assertEqual(
            "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
            self.checkpoint["institution_scope"]["P15"],
        )
        release = self.projection["release_reconciliation"]
        self.assertEqual("NOT_CREATED", release["target_core_repository"])
        self.assertEqual("NOT_CREATED", release["target_ops_repository"])
        self.assertFalse(release["provider_apply_performed"])
        self.assertFalse(release["consequential_release_performed"])
        self.assertEqual(
            "PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED",
            self.projection["provider_execution_plane_cutover"],
        )
        self.assertEqual(0, self.projection["verified_live_revenue_events"])
        self.assertFalse(self.projection["full_commercial_maturity"])
        self.assertIn(
            "READ_ONLY_OUTCOME_RECONCILIATION_RELEASE_RECONCILED",
            self.projection["stage_projection"]["C15"],
        )


if __name__ == "__main__":
    unittest.main()
