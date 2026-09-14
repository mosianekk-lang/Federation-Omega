import unittest

from ao_harmonic_v3.architecture_shadow import run_authority_only_shadow


class ForestFirstAuthorityOnlyShadowV1Tests(unittest.TestCase):
    def setUp(self):
        self.report = run_authority_only_shadow()

    def test_required_three_scenarios_run_and_pass(self):
        self.assertEqual(self.report["scenario_count"], 3)
        self.assertTrue(self.report["pass"])
        self.assertTrue(all(row["pass_state"] for row in self.report["scenarios"]))

    def test_shadow_is_a1_internal_and_non_effectful(self):
        self.assertEqual(self.report["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(self.report["external_effect"])
        self.assertFalse(self.report["provider_runtime_proved"])
        self.assertFalse(self.report["physical_migration_executed"])

    def test_shadow_cannot_retire_or_inherit_maturity(self):
        self.assertFalse(self.report["system_retirement_allowed"])
        self.assertFalse(self.report["maturity_inheritance"])
        self.assertEqual(self.report["independent_assurance_review"], "PENDING")
        self.assertEqual(self.report["promotion_state"], "SHADOW_PASS_PENDING_INDEPENDENT_ASSURANCE")

    def test_scientia_and_bible_remain_separate(self):
        scenario = next(row for row in self.report["scenarios"] if row["scenario_id"] == "C1-SCIENTIA-SEPARATION")
        self.assertTrue(scenario["checks"]["knowledge_and_runtime_layers_distinct"])
        self.assertTrue(scenario["checks"]["falsifiers_preserved"])


if __name__ == "__main__":
    unittest.main()
