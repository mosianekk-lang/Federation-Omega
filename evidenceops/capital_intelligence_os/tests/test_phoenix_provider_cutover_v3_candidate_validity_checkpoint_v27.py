from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = ROOT / "alpha_omega_commercial" / "phoenix_cutover_candidate_validity_checkpoint_v27.json"
PROJECTION_PATH = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v27.json"


class PhoenixCutoverCandidateValidityCheckpointV27Tests(unittest.TestCase):
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
            "b8f8c1d0a92e4d2edaa7a268e4f273f9a5ac596c965d73648db0f21d54fddada",
            self.canonical_hash(self.checkpoint, "checkpoint_sha256"),
        )
        self.assertEqual(
            "2fc0890014327e9a04a0d14ff9087f1facc120a63f89e4c2d9b23776cbdfd096",
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

    def test_predecessor_and_implementation_lineage_are_exact(self):
        predecessor = self.checkpoint["predecessor"]
        self.assertEqual(
            "alpha_omega_commercial/phoenix_read_only_outcome_reconciliation_checkpoint_v26.json",
            predecessor["checkpoint_file"],
        )
        self.assertEqual(
            "f8b7019885ae59f531b79e6f83d6ade78555b67409254280c3c5749e3c9f1e67",
            predecessor["checkpoint_sha256"],
        )
        self.assertEqual(
            "e328ab5a04b85da5c38eb67e288b41751bf836e0b0b0008f182e25d48cad7ada",
            predecessor["programme_projection_sha256"],
        )
        lineage = self.checkpoint["implementation_lineage"]
        self.assertEqual(235, lineage["implementation_pull_request"])
        self.assertEqual(
            "a9887d1d8bc9ce085599be5a4a20588268acb04e",
            lineage["implementation_merge_commit"],
        )
        self.assertEqual(0, lineage["workflow_change_count"])
        self.assertEqual(
            "PR_ASSOCIATED_HEAD_VERIFIED_ZERO_UNADMITTED_COMMITS",
            lineage["source_provenance_truth"],
        )

    def test_provider_native_proof_and_final_head_are_exact(self):
        admission = self.checkpoint["provider_native_admission"]
        self.assertEqual(30957599057, admission["airlock_run"])
        self.assertEqual(92154148396, admission["airlock_job"])
        self.assertEqual(8911662814, admission["airlock_artifact_id"])
        self.assertEqual([], admission["airlock_findings"])
        self.assertEqual(0, admission["unadmitted_commit_count"])
        self.assertEqual("SUCCESS", admission["public_repository_leak_guard"])
        regressions = admission["provider_control_regressions"]
        self.assertEqual("88/88_PASS", regressions["provider_cutover_v3_family"])
        self.assertEqual("6/6_PASS", regressions["cutover_candidate_validity"])
        self.assertEqual("6/6_PASS", regressions["phoenix_export_purity"])

        final_head = self.checkpoint["provider_native_final_head"]
        self.assertEqual(
            "a9887d1d8bc9ce085599be5a4a20588268acb04e",
            final_head["source_sha"],
        )
        self.assertEqual(30957671368, final_head["workflow_run"])
        self.assertEqual(92154377134, final_head["workflow_job"])
        self.assertEqual("success", final_head["conclusion"])
        self.assertEqual("phoenix-freeze/verified", final_head["commit_status"])
        self.assertEqual(8911689010, final_head["cutover_artifact"]["artifact_id"])
        self.assertEqual(8911688740, final_head["freeze_artifact"]["artifact_id"])

    def test_export_receipt_and_candidate_contract_are_exact(self):
        receipt = self.checkpoint["export_receipt"]
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertEqual("1.0.8", receipt["policy_version"])
        self.assertEqual(
            "0210763df1f0958ef596399411177881cbbf385c650bd6c5bfefe759ba4f6c7b",
            receipt["receipt_sha256"],
        )
        self.assertEqual(
            "cf246cbf0b8e2a86308a3473f140511d60331a80ae24407fed2b5e7fe2d32439",
            receipt["core"]["archive_sha256"],
        )
        self.assertEqual(
            "b20d79e619349f50586df78d24daa841d2c42b263ed79752d02a7e60b204f3a1",
            receipt["ops"]["archive_sha256"],
        )
        self.assertEqual(0, receipt["ops"]["active_workflow_count"])
        self.assertIn(
            "provider_cutover_candidate.py",
            receipt["ops"]["required_execution_files"],
        )
        contract = receipt["candidate_validity_contract"]
        self.assertEqual(
            "provider_cutover_candidate.py", contract["canonical_apply_entrypoint"]
        )
        self.assertTrue(contract["candidate_generated_after_merge"])
        self.assertTrue(contract["candidate_stored_outside_source"])
        self.assertTrue(contract["validity_computed_not_stored"])
        self.assertTrue(contract["source_drift_invalidates"])
        self.assertTrue(contract["core_archive_drift_invalidates"])
        self.assertTrue(contract["ops_archive_drift_invalidates"])
        self.assertFalse(contract["invalid_candidate_authorization_state_created"])
        self.assertFalse(contract["invalid_candidate_provider_apply_allowed"])

    def test_candidate_operational_gate_fails_closed_before_provider_use(self):
        gate = self.checkpoint["operational_proof_gate"]
        self.assertEqual("VERIFIED", gate["post_merge_candidate_generation"])
        self.assertEqual("PROHIBITED_VERIFIED", gate["candidate_manifest_source_storage"])
        self.assertEqual("VERIFIED", gate["candidate_integrity_hash"])
        self.assertEqual(
            "COMPUTED_NOT_STORED_VERIFIED",
            gate["candidate_validity_semantics"],
        )
        self.assertEqual("VERIFIED", gate["source_drift_fail_closed"])
        self.assertEqual("VERIFIED", gate["archive_drift_fail_closed"])
        self.assertEqual("VERIFIED", gate["decision_mismatch_fail_closed"])
        self.assertFalse(gate["invalid_candidate_authorization_state_created"])
        self.assertFalse(gate["invalid_candidate_provider_call_allowed"])
        self.assertFalse(gate["provider_apply_performed"])
        self.assertFalse(gate["provider_mutation_performed"])
        self.assertFalse(gate["external_repository_created"])

    def test_execution_freeze_and_private_drive_release_are_exact(self):
        freeze = self.checkpoint["execution_freeze_receipt"]
        self.assertEqual("VERIFIED", freeze["status"])
        self.assertEqual(30957671368, freeze["run_id"])
        self.assertEqual([], freeze["unexpected_active"])
        self.assertEqual([], freeze["missing_required"])
        self.assertFalse(freeze["source_mutation_attempted"])

        drive = self.checkpoint["google_drive_release"]
        self.assertEqual(
            "1KWKL_k2_g-VfJdZPV1evrJs-oLq_gaclOXDtn0xmAYs",
            drive["file_id"],
        )
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(5972, drive["text_export_size_bytes"])
        self.assertEqual(
            "ae0abc5e8a9d549d9e79cc6f8659ff32227daef6f4fc0efa46e38bb84a4f224c",
            drive["text_export_sha256"],
        )

    def test_external_commercial_truth_and_owner_authority_remain_fail_closed(self):
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

        authority = self.checkpoint["owner_authority"]
        self.assertEqual("OWNER_RESERVED", authority["financial_commitments"])
        self.assertEqual("OWNER_RESERVED", authority["contracts"])
        self.assertEqual("OWNER_RESERVED", authority["external_communications"])
        self.assertEqual(
            "OWNER_RESERVED_FRESH_EXACT_AUTHORIZATION_REQUIRED",
            authority["execution_plane_cutover"],
        )

    def test_release_projection_preserves_provider_and_market_boundaries(self):
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
            "CUTOVER_CANDIDATE_VALIDITY_RELEASE_RECONCILED",
            self.projection["stage_projection"]["C15"],
        )


if __name__ == "__main__":
    unittest.main()
