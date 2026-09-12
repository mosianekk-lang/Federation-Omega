import unittest

from ao_harmonic_v3.forest_integrity_equivalence import (
    ForestIntegrityEquivalenceHarness,
    reference_scenarios,
)


class ForestIntegrityEquivalenceTests(unittest.TestCase):
    def setUp(self):
        self.scenarios = reference_scenarios()
        self.harness = ForestIntegrityEquivalenceHarness()

    def test_reference_suite_has_no_unexplained_divergence(self):
        report = self.harness.run(self.scenarios)
        self.assertEqual(report.scenario_count, 4)
        self.assertEqual(report.preserved_count, 2)
        self.assertEqual(report.safety_tightened_count, 2)
        self.assertEqual(report.unexplained_divergence_count, 0)
        self.assertTrue(report.promotion_ready)
        self.assertFalse(report.external_effect)
        self.assertFalse(report.runtime_rewired)
        self.assertEqual(report.authority_ceiling, "A1_INTERNAL")
        self.assertEqual(
            report.truth_class,
            "DETERMINISTIC_SHADOW_EQUIVALENCE_NOT_OPERATIONAL_OUTCOME_PROOF",
        )

    def test_admitted_fixture_exposes_missing_admissibility_and_unbound_truth(self):
        row = self.harness.evaluate(self.scenarios[0])
        self.assertEqual(row.scenario_id, "ADMITTED-LEGACY-FIXTURE")
        self.assertEqual(row.legacy_selected_path, "REUSE-PRIMARY")
        self.assertIsNone(row.typed_selected_path)
        self.assertEqual(row.classification, "SAFETY_TIGHTENED")
        self.assertEqual(row.routes_with_missing_admissibility, 2)
        self.assertEqual(row.missing_admissibility_fields, 14)
        self.assertEqual(row.declared_true_unbound_count, 7)
        self.assertEqual(row.unverified_evidence_count, 2)

    def test_explicit_admissibility_preserves_best_route(self):
        row = self.harness.evaluate(self.scenarios[1])
        self.assertEqual(row.legacy_selected_path, "REUSE-PRIMARY")
        self.assertEqual(row.typed_selected_path, "REUSE-PRIMARY")
        self.assertTrue(row.selection_preserved)
        self.assertEqual(row.classification, "PRESERVED")
        self.assertEqual(row.missing_admissibility_fields, 0)

    def test_unauthorised_high_score_route_is_excluded_before_ranking(self):
        row = self.harness.evaluate(self.scenarios[2])
        self.assertEqual(row.legacy_selected_path, "UNAUTHORISED-HIGH")
        self.assertEqual(row.typed_selected_path, "AUTHORISED-LOWER")
        self.assertFalse(row.selection_preserved)
        self.assertEqual(row.classification, "SAFETY_TIGHTENED")
        self.assertEqual(row.missing_admissibility_fields, 0)

    def test_consequential_hold_is_preserved(self):
        row = self.harness.evaluate(self.scenarios[3])
        self.assertTrue(row.legacy_owner_hold)
        self.assertFalse(row.typed_release_ready)
        self.assertEqual(row.classification, "PRESERVED")

    def test_expected_classifications_match_harness(self):
        for scenario in self.scenarios:
            with self.subTest(scenario=scenario.scenario_id):
                row = self.harness.evaluate(scenario)
                self.assertEqual(row.classification, scenario.expected_classification)


if __name__ == "__main__":
    unittest.main()
