from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_PATH = ROOT / "alpha_omega_commercial" / "phoenix_provider_authority_boundary_checkpoint_v28.json"
PROJECTION_PATH = ROOT / "alpha_omega_commercial" / "programme_maturity_effective_v28.json"
APPLY_ENTRYPOINT_PATH = ROOT / "phoenix" / "ops-template" / "governance" / "APPLY_ENTRYPOINT.json"
AUTHORITY_CONTRACT_PATH = ROOT / "phoenix" / "ops-template" / "governance" / "PROVIDER_AUTHORITY_PROBE_CONTRACT.json"
OPS_CONTRACT_PATH = ROOT / "phoenix" / "ops-template" / "governance" / "OPS_CONTRACT.json"


class PhoenixProviderAuthorityBoundaryCheckpointV28Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        cls.projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        cls.apply_entrypoint = json.loads(APPLY_ENTRYPOINT_PATH.read_text(encoding="utf-8"))
        cls.authority_contract = json.loads(AUTHORITY_CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.ops_contract = json.loads(OPS_CONTRACT_PATH.read_text(encoding="utf-8"))

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
            "ca3424575d73d080fb383dd4d2e6c10b2ccf33135c648372307f95a071d16e7e",
            self.canonical_hash(self.checkpoint, "checkpoint_sha256"),
        )
        self.assertEqual(
            "f53b80ad09ed0e6372d441915da4ad83a49e88fb01b1628a81877e36169440c7",
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
            "alpha_omega_commercial/phoenix_cutover_candidate_validity_checkpoint_v27.json",
            predecessor["checkpoint_file"],
        )
        self.assertEqual(
            "b8f8c1d0a92e4d2edaa7a268e4f273f9a5ac596c965d73648db0f21d54fddada",
            predecessor["checkpoint_sha256"],
        )
        self.assertEqual(
            "2fc0890014327e9a04a0d14ff9087f1facc120a63f89e4c2d9b23776cbdfd096",
            predecessor["programme_projection_sha256"],
        )
        lineage = self.checkpoint["implementation_lineage"]
        self.assertEqual(237, lineage["capability_pull_request"])
        self.assertEqual(
            "613c1c19010c3484abf3de5c90ce29930889aae2",
            lineage["capability_merge_commit"],
        )
        self.assertEqual(240, lineage["current_main_export_contract_pull_request"])
        self.assertEqual(
            "7065290d98fa384858b8d609df4960a35ece563b",
            lineage["current_main_export_contract_merge_commit"],
        )
        self.assertEqual(0, lineage["workflow_change_count"])
        self.assertEqual(
            "PR_ASSOCIATED_HEAD_VERIFIED_ZERO_UNADMITTED_COMMITS",
            lineage["source_provenance_truth"],
        )

    def test_provider_native_admission_and_final_head_are_exact(self):
        admission = self.checkpoint["provider_native_admission"]
        self.assertEqual(30960807002, admission["airlock_run"])
        self.assertEqual(92164099868, admission["airlock_job"])
        self.assertEqual(8912854487, admission["airlock_artifact_id"])
        self.assertEqual([], admission["airlock_findings"])
        self.assertEqual(0, admission["unadmitted_commit_count"])
        self.assertEqual("SUCCESS", admission["public_repository_leak_guard"])
        regressions = admission["provider_control_regressions"]
        self.assertEqual("113/113_PASS", regressions["provider_cutover_v3_family"])
        self.assertEqual("7/7_PASS", regressions["authority_probe"])
        self.assertEqual("5/5_PASS", regressions["authority_bound_entrypoint"])
        self.assertEqual("4/4_PASS", regressions["authority_export_contract"])
        self.assertEqual("6/6_PASS", regressions["phoenix_export_purity"])

        final_head = self.checkpoint["provider_native_final_head"]
        self.assertEqual(
            "7065290d98fa384858b8d609df4960a35ece563b",
            final_head["source_sha"],
        )
        self.assertEqual(30960914268, final_head["workflow_run"])
        self.assertEqual(92164426068, final_head["workflow_job"])
        self.assertEqual("success", final_head["conclusion"])
        self.assertEqual("phoenix-freeze/verified", final_head["commit_status"])
        self.assertEqual(8912892480, final_head["cutover_artifact"]["artifact_id"])
        self.assertEqual(8912892183, final_head["freeze_artifact"]["artifact_id"])

    def test_export_receipt_and_authority_contract_are_exact(self):
        receipt = self.checkpoint["export_receipt"]
        self.assertEqual("VERIFIED", receipt["status"])
        self.assertEqual("1.0.9", receipt["policy_version"])
        self.assertEqual(
            "9087683799930e54bb8c622b34eb90a245f43fa0a92e9cec6fce4d00f4210fad",
            receipt["receipt_sha256"],
        )
        self.assertEqual(
            "cc8e3477d44a68934aef4a14a8f0d5ad80bf7fa3057102691918a3ce2e08883e",
            receipt["core"]["archive_sha256"],
        )
        self.assertEqual(
            "ef2865a4477e8fb5e5ce848940d819a13baae93a1976e748ce2583c7b16c2c83",
            receipt["ops"]["archive_sha256"],
        )
        self.assertEqual(0, receipt["ops"]["active_workflow_count"])
        self.assertIn("provider_authority_probe.py", receipt["ops"]["required_execution_files"])
        self.assertIn(
            "provider_cutover_authority_bound.py",
            receipt["ops"]["required_execution_files"],
        )
        contract = receipt["provider_authority_contract"]
        self.assertEqual(
            "provider_cutover_authority_bound.py",
            contract["canonical_apply_entrypoint"],
        )
        self.assertTrue(contract["authority_receipt_required"])
        self.assertTrue(contract["probe_get_only"])
        self.assertTrue(contract["selected_repository_installation_blocked"])
        self.assertEqual("all", contract["installation_repository_selection_required"])
        self.assertFalse(contract["credential_value_recorded"])

    def test_exported_governance_names_owner_authority_bound_route_as_canonical(self):
        self.assertEqual(
            "provider_cutover_owner_authority_bound.py",
            self.apply_entrypoint["canonical_apply_entrypoint"],
        )
        self.assertTrue(
            self.apply_entrypoint["owner_authorization_provider_receipt_hash_binding"]
        )
        self.assertTrue(
            self.apply_entrypoint["owner_authorization_repository_creation_endpoint_binding"]
        )
        self.assertFalse(
            self.apply_entrypoint[
                "owner_authorization_external_commercial_gate_advancement_allowed"
            ]
        )
        self.assertTrue(self.apply_entrypoint["provider_authority_receipt_required"])
        self.assertTrue(self.apply_entrypoint["provider_authority_probe_get_only"])
        self.assertTrue(
            self.apply_entrypoint["provider_authority_selected_repository_installation_blocked"]
        )
        self.assertEqual(
            "provider_authority_probe.py",
            self.apply_entrypoint["provider_authority_probe"],
        )

        self.assertTrue(self.authority_contract["probe_get_only"])
        self.assertFalse(self.authority_contract["credential_value_recorded"])
        self.assertFalse(self.authority_contract["provider_mutation_performed"])
        self.assertEqual(
            "all",
            self.authority_contract["installation_template_route"][
                "repository_selection_required"
            ],
        )
        self.assertEqual(
            "write",
            self.authority_contract["installation_template_route"][
                "administration_permission_required"
            ],
        )
        self.assertEqual(
            "AUTHORITY_BLOCKED_EXACT_REMEDIATION_REQUIRED",
            self.authority_contract["selected_repository_installation_status"],
        )

        self.assertEqual(
            "provider_cutover_owner_authority_bound.py",
            self.ops_contract["canonical_apply_entrypoint"],
        )
        rules = self.ops_contract["authority_rules"]
        self.assertTrue(
            rules["owner_authorization_provider_receipt_hash_binding_required"]
        )
        self.assertTrue(
            rules["owner_authorization_repository_creation_endpoint_binding_required"]
        )
        self.assertFalse(
            rules["owner_authorization_external_commercial_gate_advancement_allowed"]
        )
        self.assertTrue(rules["provider_authority_receipt_required"])
        self.assertTrue(rules["provider_authority_probe_get_only"])
        self.assertTrue(rules["provider_authority_mode_must_match_decision"])
        self.assertFalse(rules["source_repository_mutation"])

    def test_live_provider_authority_readback_is_truthful_and_fail_closed(self):
        readback = self.checkpoint["provider_authority_readback"]
        self.assertTrue(readback["fresh_readback_performed"])
        self.assertEqual("mosianekk-lang", readback["authenticated_account_login"])
        self.assertEqual(149462480, readback["connected_installation_id"])
        self.assertEqual(1, readback["installed_repository_count"])
        self.assertEqual(
            ["mosianekk-lang/Federation-Omega"],
            readback["installed_repositories"],
        )
        self.assertEqual(
            "NOT_FOUND_NOT_CLAIMED_CREATED",
            readback["target_core_repository"],
        )
        self.assertEqual(
            "NOT_FOUND_NOT_CLAIMED_CREATED",
            readback["target_ops_repository"],
        )
        self.assertEqual(
            "PROVIDER_BLOCKED_SELECTED_REPOSITORY_INSTALLATION_OR_USER_SCOPED_ADMIN_AUTHORITY_REQUIRED",
            readback["provider_apply_authority"],
        )
        self.assertFalse(readback["provider_mutation_performed"])

        gate = self.checkpoint["operational_proof_gate"]
        self.assertEqual("VERIFIED", gate["provider_authority_probe_get_only"])
        self.assertTrue(gate["authority_receipt_required_before_apply"])
        self.assertEqual(
            "VERIFIED",
            gate["selected_repository_installation_fail_closed"],
        )
        self.assertFalse(gate["blocked_authority_authorization_state_created"])
        self.assertFalse(gate["blocked_authority_provider_call_allowed"])
        self.assertFalse(gate["provider_apply_performed"])
        self.assertFalse(gate["provider_mutation_performed"])
        self.assertFalse(gate["external_repository_created"])

    def test_execution_freeze_and_private_drive_release_are_exact(self):
        freeze = self.checkpoint["execution_freeze_receipt"]
        self.assertEqual("VERIFIED", freeze["status"])
        self.assertEqual(30960914268, freeze["run_id"])
        self.assertEqual([], freeze["unexpected_active"])
        self.assertEqual([], freeze["missing_required"])
        self.assertFalse(freeze["source_mutation_attempted"])

        drive = self.checkpoint["google_drive_release"]
        self.assertEqual(
            "1PSTw8mxxZxEJ6vNWUuNKvztQOGS4ZyKzBwa_nxSYQ_o",
            drive["file_id"],
        )
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(7319, drive["text_export_size_bytes"])
        self.assertEqual(
            "102a25cb5d19c7436790ef087288aff8ba2f51e1e151867cae32c31c32adb52c",
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

    def test_release_projection_preserves_provider_market_and_institution_boundaries(self):
        release = self.projection["release_reconciliation"]
        self.assertEqual("NOT_CREATED", release["target_core_repository"])
        self.assertEqual("NOT_CREATED", release["target_ops_repository"])
        self.assertFalse(release["provider_apply_performed"])
        self.assertFalse(release["consequential_release_performed"])
        self.assertEqual(
            "PROVIDER_BLOCKED_SELECTED_REPOSITORY_INSTALLATION_OR_USER_SCOPED_ADMIN_AUTHORITY_REQUIRED",
            self.projection["provider_execution_plane_cutover"],
        )
        self.assertEqual(0, self.projection["verified_live_revenue_events"])
        self.assertFalse(self.projection["full_commercial_maturity"])
        self.assertEqual(
            "UNVERIFIED_SCOPE_HELD",
            self.projection["institution_scope"]["institution_v3_google_drive_publication"],
        )
        self.assertIn(
            "PROVIDER_AUTHORITY_BOUNDARY_RELEASE_RECONCILED",
            self.projection["stage_projection"]["C15"],
        )


if __name__ == "__main__":
    unittest.main()
