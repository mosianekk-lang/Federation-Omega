import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "governance" / "ao_harmonic_forest_first_shadow_equivalence_plan_v1.json"


class ForestFirstShadowEquivalencePlanV1Tests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.cohorts = {row["id"]: row for row in self.plan["cohorts"]}

    def test_all_eleven_candidates_are_partitioned_once(self):
        systems = [system for cohort in self.plan["cohorts"] for system in cohort["systems"]]
        self.assertEqual(len(systems), 11)
        self.assertEqual(len(systems), len(set(systems)))

    def test_formation_is_last_and_requires_public_api_proof(self):
        cohort = self.cohorts["C5_FORMATION_LAST"]
        self.assertEqual(cohort["systems"], ["FORMATION-OMEGA Unified Powerhouse"])
        self.assertIn("public_api_freeze", cohort["special_checks"])
        self.assertIn("exact_head_admission_before_any_supersession", cohort["special_checks"])

    def test_shadow_cannot_promote_provider_effect_or_retirement(self):
        self.assertIn("provider_effect_from_shadow", self.plan["global_acceptance"]["prohibited_claims"])
        self.assertFalse(self.plan["promotion_gate"]["automatic_source_move"])
        self.assertFalse(self.plan["promotion_gate"]["automatic_retirement"])

    def test_c1_c2_and_c3_have_provider_hosted_source_proof_only(self):
        boundary = self.plan["truth_boundary"]
        self.assertTrue(boundary["shadow_run_executed"])
        self.assertEqual(
            set(boundary["shadow_scope"]),
            {"C1_AUTHORITY_ONLY", "C2_DOMAIN_COMPATIBILITY", "C3_RECOVERY_FORMATION"},
        )
        self.assertTrue(boundary["provider_hosted_source_shadow_proved"])
        self.assertFalse(boundary["provider_runtime_shadow_proved"])
        self.assertEqual(boundary["independent_assurance_review"], "PENDING")
        self.assertFalse(boundary["physical_migration_executed"])
        self.assertFalse(boundary["runtime_changed"])
        self.assertFalse(boundary["provider_effect"])
        for cohort in ("C1_AUTHORITY_ONLY", "C2_DOMAIN_COMPATIBILITY", "C3_RECOVERY_FORMATION"):
            self.assertEqual(
                self.plan["cohort_status"][cohort],
                "PROVIDER_HOSTED_SOURCE_PASS_PENDING_INDEPENDENT_ASSURANCE",
            )
        self.assertEqual(self.plan["cohort_status"]["C4_HIGH_COUPLING_POLICY_VALIDATION"], "NOT_RUN")
        self.assertEqual(self.plan["cohort_status"]["C5_FORMATION_LAST"], "NOT_RUN")

    def test_c1_c2_and_c3_receipts_are_fail_safe_and_no_fallback_was_needed(self):
        receipts = self.plan["proof_receipts"]
        self.assertEqual(self.plan["base_main_sha"], "d6603e980ed5ad9c7c111a1561cf745de7c7b4c9")
        self.assertEqual(self.plan["exact_head_sha"], "e36994cb2da6fa2158615b6943b4a90e600efb87")
        for cohort in ("C1_C2", "C3"):
            proof = receipts[cohort]
            self.assertEqual(proof["blocking_proofs_passed"], 14)
            self.assertEqual(proof["blocking_failures"], 0)
            self.assertEqual(proof["unmapped_production_paths"], 0)
            self.assertFalse(proof["fallback_full_suite_activated"])
            self.assertEqual(proof["shadow_escape_candidates"], 0)


if __name__ == "__main__":
    unittest.main()
