import json
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "governance" / "ao_harmonic_forest_first_shadow_equivalence_plan_v1.json"
SOURCE_PASS = "PROVIDER_HOSTED_SOURCE_PASS_PENDING_INDEPENDENT_ASSURANCE"


class ForestFirstShadowEquivalencePlanV1Tests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.cohorts = {row["id"]: row for row in self.plan["cohorts"]}

    def test_all_eleven_candidates_are_partitioned_once(self):
        systems = [system for cohort in self.plan["cohorts"] for system in cohort["systems"]]
        self.assertEqual(len(systems), 11)
        self.assertEqual(len(systems), len(set(systems)))

    def test_formation_is_last_and_requires_public_api_proof(self):
        cohort_ids = [row["id"] for row in self.plan["cohorts"]]
        self.assertEqual(cohort_ids[-1], "C5_FORMATION_LAST")
        cohort = self.cohorts["C5_FORMATION_LAST"]
        self.assertEqual(cohort["systems"], ["FORMATION-OMEGA Unified Powerhouse"])
        self.assertIn("public_api_freeze", cohort["special_checks"])
        self.assertIn("exact_head_admission_before_any_supersession", cohort["special_checks"])

    def test_shadow_cannot_promote_provider_effect_or_retirement(self):
        prohibited = set(self.plan["global_acceptance"]["prohibited_claims"])
        self.assertIn("provider_effect_from_shadow", prohibited)
        self.assertIn("maturity_inheritance", prohibited)
        self.assertIn("system_retirement_before_dual_run", prohibited)
        self.assertFalse(self.plan["promotion_gate"]["automatic_source_move"])
        self.assertFalse(self.plan["promotion_gate"]["automatic_retirement"])

    def test_completed_cohorts_preserve_source_only_truth_boundary(self):
        boundary = self.plan["truth_boundary"]
        self.assertTrue(boundary["shadow_run_executed"])
        self.assertTrue(boundary["provider_hosted_source_shadow_proved"])
        self.assertFalse(boundary["provider_runtime_shadow_proved"])
        self.assertEqual(boundary["independent_assurance_review"], "PENDING")
        self.assertFalse(boundary["physical_migration_executed"])
        self.assertFalse(boundary["runtime_changed"])
        self.assertFalse(boundary["provider_effect"])

        completed = (
            "C1_AUTHORITY_ONLY",
            "C2_DOMAIN_COMPATIBILITY",
            "C3_RECOVERY_FORMATION",
            "C4_HIGH_COUPLING_POLICY_VALIDATION",
        )
        for cohort in completed:
            self.assertEqual(self.plan["cohort_status"][cohort], SOURCE_PASS)
            self.assertIn(cohort, boundary["shadow_scope"])

        self.assertIn(
            self.plan["cohort_status"]["C5_FORMATION_LAST"],
            {"IN_PROGRESS_NOT_YET_PROVEN", SOURCE_PASS},
        )
        if self.plan["cohort_status"]["C5_FORMATION_LAST"] == SOURCE_PASS:
            self.assertIn("C5_FORMATION_LAST", boundary["shadow_scope"])

    def test_completed_receipts_are_fail_safe_without_historical_sha_pinning(self):
        receipts = self.plan["proof_receipts"]
        self.assertRegex(self.plan["base_main_sha"], r"^[0-9a-f]{40}$")
        self.assertRegex(self.plan["exact_head_sha"], r"^[0-9a-f]{40}$")

        expected_receipts = ("C1_C2", "C3", "C4")
        for cohort in expected_receipts:
            proof = receipts[cohort]
            self.assertGreater(proof["blocking_proofs_passed"], 0)
            self.assertEqual(proof["blocking_failures"], 0)
            self.assertEqual(proof["unmapped_production_paths"], 0)
            self.assertFalse(proof["fallback_full_suite_activated"])
            self.assertEqual(proof["shadow_escape_candidates"], 0)
            self.assertRegex(proof["artifact_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(proof["proofos_manifest_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(proof["proofos_report_sha256"], r"^[0-9a-f]{64}$")

        if self.plan["cohort_status"]["C5_FORMATION_LAST"] == SOURCE_PASS:
            self.assertIn("C5", receipts)


if __name__ == "__main__":
    unittest.main()
