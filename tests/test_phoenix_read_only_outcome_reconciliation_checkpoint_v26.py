from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMERCIAL = ROOT / "alpha_omega_commercial"
CHECKPOINT = COMMERCIAL / "phoenix_read_only_outcome_reconciliation_checkpoint_v26.json"
PROJECTION = COMMERCIAL / "programme_maturity_effective_v26.json"


def canonical_sha256(payload: dict, field: str) -> str:
    body = dict(payload)
    body.pop(field)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class PhoenixReadOnlyOutcomeReconciliationCheckpointV26Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        cls.projection = json.loads(PROJECTION.read_text(encoding="utf-8"))

    def test_01_checkpoint_and_projection_are_hash_bound(self) -> None:
        self.assertEqual(
            self.checkpoint["checkpoint_sha256"],
            canonical_sha256(self.checkpoint, "checkpoint_sha256"),
        )
        self.assertEqual(
            self.projection["projection_sha256"],
            canonical_sha256(self.projection, "projection_sha256"),
        )

    def test_02_dependency_order_and_service_first_policy_are_preserved(self) -> None:
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

    def test_03_predecessor_v25_is_exact(self) -> None:
        predecessor = self.checkpoint["predecessor"]
        self.assertEqual(
            "5a534f37b16c2d0f5eee614d9a5b3a5bd1d677cfca79478c7f90ebb36de28410",
            predecessor["checkpoint_sha256"],
        )
        self.assertEqual(
            "27913b8e4666a0208fca6d5d317e1470e9ad18b2b055fc9bce38bd9dc456463f",
            predecessor["programme_projection_sha256"],
        )
        self.assertEqual(
            "alpha_omega_commercial/programme_maturity_effective_v25.json",
            self.projection["predecessor_projection"],
        )

    def test_04_provider_native_admission_is_exact_and_complete(self) -> None:
        admission = self.checkpoint["provider_native_admission"]
        self.assertEqual(30956205046, admission["airlock_run"])
        self.assertEqual(92149720882, admission["airlock_job"])
        self.assertEqual(8911112188, admission["airlock_artifact_id"])
        self.assertEqual(
            "sha256:3a18c8d27cc6a431052edf88c581c65784742477a2178d5ad254b6057db5970a",
            admission["airlock_artifact_digest"],
        )
        self.assertEqual("PASS", admission["airlock_status"])
        self.assertEqual([], admission["airlock_findings"])
        self.assertEqual(0, admission["changed_workflow_count"])
        self.assertEqual(0, admission["unadmitted_commit_count"])
        self.assertEqual("SUCCESS", admission["public_repository_leak_guard"])
        regressions = admission["regressions"]
        self.assertEqual(74, regressions["provider_cutover_v3_family_tests"])
        self.assertEqual(9, regressions["v26_outcome_reconciler_tests"])
        self.assertEqual("PASS", regressions["result"])

    def test_05_current_main_phoenix_proof_and_artifacts_are_exact(self) -> None:
        proof = self.checkpoint["provider_native_final_head"]
        self.assertEqual(
            "c6354d9379dd0abc1f2d0035dec27e21fde6da93",
            proof["source_sha"],
        )
        self.assertEqual(30956275861, proof["workflow_run"])
        self.assertEqual(92149950357, proof["workflow_job"])
        self.assertEqual("success", proof["conclusion"])
        self.assertEqual("phoenix-freeze/verified", proof["commit_status"])
        self.assertEqual(
            "sha256:aebaf8e678bb92ec5e1fc78f2a13b2f1a21cbd6f0d168b945f7423aeb43f01e9",
            proof["cutover_artifact"]["artifact_digest"],
        )
        self.assertEqual(
            "sha256:32b4bc04cbd59b972369addf981799d486054d6b7a13e4e28f37133a22f7fdcc",
            proof["freeze_artifact"]["artifact_digest"],
        )

    def test_06_export_contains_get_only_reconciler_and_no_apply_claim(self) -> None:
        receipt = self.checkpoint["export_receipt"]
        self.assertEqual("1.0.8", receipt["policy_version"])
        self.assertEqual(
            "c8d533526cea1746ee8ac85401238a8ab02cb35c3c511486a5e568cdf85a564e",
            receipt["core"]["archive_sha256"],
        )
        self.assertEqual(
            "83f4e0c34f93253e933db369e4298cbe008011e9a8e281948b5841fd62031a7e",
            receipt["ops"]["archive_sha256"],
        )
        self.assertEqual(0, receipt["core"]["workflow_count"])
        self.assertEqual(0, receipt["ops"]["active_workflow_count"])
        self.assertIn(
            "provider_cutover_outcome_reconciler.py",
            receipt["ops"]["required_execution_and_recovery_files"],
        )
        engine = receipt["provider_cutover_engine"]
        self.assertEqual("3.3", engine["version"])
        self.assertTrue(engine["read_only_outcome_reconciliation"])
        self.assertFalse(engine["outcome_reconciliation_mutation_allowed"])
        self.assertFalse(engine["unknown_outcome_automatic_retry"])
        self.assertFalse(engine["provider_apply_performed"])
        self.assertTrue(
            (ROOT / "phoenix" / "provider_cutover_outcome_reconciler.py").is_file()
        )

    def test_07_execution_freeze_and_drive_readback_are_exact(self) -> None:
        freeze = self.checkpoint["execution_freeze_receipt"]
        self.assertEqual("VERIFIED", freeze["status"])
        self.assertEqual(140, freeze["disabled_total_after"])
        self.assertEqual([], freeze["unexpected_active"])
        self.assertEqual([], freeze["missing_required"])
        self.assertFalse(freeze["source_mutation_attempted"])

        drive = self.checkpoint["google_drive_release"]
        self.assertEqual("VERIFIED", drive["readback"])
        self.assertFalse(drive["shared"])
        self.assertEqual("mosianekk@gmail.com", drive["owner"])
        self.assertEqual(4147, drive["text_export_size_bytes"])
        self.assertEqual(
            "dcc9621a4d25f1ab68cc4d3602606ab75df207869fbb4b4bf88f751af0c5183c",
            drive["text_export_sha256"],
        )

    def test_08_operational_gate_is_fail_closed_and_truthful(self) -> None:
        gate = self.checkpoint["operational_proof_gate"]
        self.assertEqual("VERIFIED", gate["get_only_provider_client_surface"])
        self.assertEqual("VERIFIED", gate["exact_authorized_archive_binding"])
        self.assertEqual(
            "DISABLED_VERIFIED",
            gate["unknown_provider_outcome_automatic_retry"],
        )
        self.assertFalse(gate["provider_apply_performed"])
        self.assertEqual("NOT_PROVEN", gate["external_repository_created"])
        self.assertEqual(
            "PROVIDER_PROOF_REQUIRED_AFTER_OWNER_AUTHORISED_APPLY",
            gate["live_provider_outcome_reconciliation"],
        )
        self.assertEqual(
            "PROVIDER_BLOCKED_FRESH_AUTHORISED_APPLY_REQUIRED",
            self.projection["provider_execution_plane_cutover"],
        )

    def test_09_external_commercial_gates_and_owner_authority_remain_closed(self) -> None:
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
        self.assertEqual(
            "CROSS_PROGRAMME_RECONCILIATION_VERIFIED_NO_PROVIDER_WRITEBACK",
            self.checkpoint["institution_scope"]["P13"],
        )
        self.assertEqual(
            "INSTITUTIONAL_READINESS_PRESERVED_EXTERNAL_COMPLETION_BLOCKED",
            self.checkpoint["institution_scope"]["P15"],
        )
        self.assertTrue(
            all(
                value.startswith("OWNER_RESERVED")
                for value in self.checkpoint["owner_authority"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
