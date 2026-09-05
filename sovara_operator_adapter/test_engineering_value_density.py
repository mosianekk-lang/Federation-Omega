import unittest

from sovara_operator_adapter.engineering_value_density import (
    ValueDensitySnapshot,
    compare_value_density,
)


class EngineeringValueDensityTests(unittest.TestCase):
    def setUp(self):
        self.runnable = ValueDensitySnapshot(
            "FIRST_RUNNABLE",
            added_lines=257,
            distinct_files=4,
            canonical_behavior_tests=5,
            control_tables=14,
        )
        self.current = ValueDensitySnapshot(
            "CURRENT_SOVEREIGN",
            added_lines=2908,
            distinct_files=16,
            canonical_behavior_tests=53,
            control_tables=36,
            execution_surface_classes_proven=2,
        )

    def test_literal_birth_can_have_no_test_denominator(self):
        birth = ValueDensitySnapshot("BIRTH", 157, 1, 0, 14)
        self.assertIsNone(birth.source_test_density_per_kloc)
        self.assertIsNone(birth.lines_per_canonical_test)

    def test_first_runnable_density_reproduces(self):
        self.assertAlmostEqual(self.runnable.source_test_density_per_kloc, 19.4552529)
        self.assertEqual(self.runnable.lines_per_canonical_test, 51.4)

    def test_current_density_reproduces(self):
        self.assertAlmostEqual(self.current.source_test_density_per_kloc, 18.2255846)
        self.assertAlmostEqual(self.current.canonical_tests_per_control_table, 53 / 36)

    def test_growth_vector_reproduces_current_measurement(self):
        delta = compare_value_density(
            self.runnable,
            self.current,
            compensating_verified_value_gain=True,
        )
        self.assertAlmostEqual(delta.code_growth_factor, 2908 / 257)
        self.assertAlmostEqual(delta.test_growth_factor, 53 / 5)
        self.assertAlmostEqual(delta.proof_code_growth_ratio, 0.9367950481)
        self.assertAlmostEqual(delta.source_test_density_change_pct, -6.3204952)
        self.assertEqual(delta.execution_surface_breadth_delta, 2)
        self.assertEqual(delta.verdict, "BALANCED_GROWTH_WITH_SOURCE_DENSITY_WATCH")
        self.assertFalse(delta.authorizes_pruning)

    def test_critical_regression_overrides_density(self):
        current = ValueDensitySnapshot("BAD", 300, 5, 20, 15, critical_regression=True)
        delta = compare_value_density(
            self.runnable, current, compensating_verified_value_gain=True
        )
        self.assertEqual(delta.verdict, "HOLD_CRITICAL_REGRESSION")

    def test_stale_proof_overrides_density(self):
        current = ValueDensitySnapshot("STALE", 300, 5, 20, 15, proof_current=False)
        delta = compare_value_density(
            self.runnable, current, compensating_verified_value_gain=True
        )
        self.assertEqual(delta.verdict, "HOLD_STALE_PROOF")

    def test_unknown_material_cost_overrides_density(self):
        current = ValueDensitySnapshot("COST", 300, 5, 20, 15, material_cost_known=False)
        delta = compare_value_density(
            self.runnable, current, compensating_verified_value_gain=True
        )
        self.assertEqual(delta.verdict, "HOLD_UNKNOWN_MATERIAL_COST")

    def test_two_uncompensated_dilution_checkpoints_hold_expansion(self):
        diluted = ValueDensitySnapshot("DILUTED", 800, 8, 6, 18)
        delta = compare_value_density(
            self.runnable,
            diluted,
            compensating_verified_value_gain=False,
            consecutive_value_dilution_checkpoints=2,
        )
        self.assertEqual(delta.verdict, "HOLD_ARCHITECTURE_EXPANSION")
        self.assertFalse(delta.authorizes_pruning)

    def test_negative_density_without_verified_compensation_is_watch(self):
        diluted = ValueDensitySnapshot("WATCH", 800, 8, 10, 18)
        delta = compare_value_density(
            self.runnable,
            diluted,
            compensating_verified_value_gain=False,
            consecutive_value_dilution_checkpoints=1,
        )
        self.assertEqual(delta.verdict, "SOURCE_DENSITY_WATCH")


if __name__ == "__main__":
    unittest.main()
