import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "governance" / "forest_first_shadow_equivalence_plan_v1.json"


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

    def test_no_shadow_has_run_yet(self):
        boundary = self.plan["truth_boundary"]
        self.assertFalse(boundary["shadow_run_executed"])
        self.assertFalse(boundary["physical_migration_executed"])
        self.assertFalse(boundary["runtime_changed"])
        self.assertFalse(boundary["provider_effect"])


if __name__ == "__main__":
    unittest.main()
