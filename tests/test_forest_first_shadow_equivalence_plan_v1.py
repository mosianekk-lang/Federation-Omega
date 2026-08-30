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

    def test_only_c1_shadow_has_run_and_remains_bounded(self):
        boundary = self.plan["truth_boundary"]
        self.assertTrue(boundary["shadow_run_executed"])
        self.assertEqual(boundary["shadow_scope"], "C1_DETERMINISTIC_LOCAL_A1_INTERNAL_ONLY")
        self.assertFalse(boundary["provider_hosted_shadow_proved"])
        self.assertFalse(boundary["physical_migration_executed"])
        self.assertFalse(boundary["runtime_changed"])
        self.assertFalse(boundary["provider_effect"])
        self.assertEqual(self.plan["cohort_status"]["C1_AUTHORITY_ONLY"], "DETERMINISTIC_LOCAL_PASS_PENDING_INDEPENDENT_ASSURANCE")
        self.assertTrue(all(
            self.plan["cohort_status"][cohort] == "NOT_RUN"
            for cohort in ("C2_DOMAIN_COMPATIBILITY","C3_RECOVERY_FORMATION","C4_HIGH_COUPLING_POLICY_VALIDATION","C5_FORMATION_LAST")
        ))


if __name__ == "__main__":
    unittest.main()
