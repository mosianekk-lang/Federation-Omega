from __future__ import annotations

import unittest

from evidenceops.lex_omega.forest_first_shadow import build_shadow_cases, run_shadow


class ForestFirstShadowAirlockTests(unittest.TestCase):
    def test_all_seeded_shadow_cases_match_expected_forest_first_outcomes(self) -> None:
        report = run_shadow()
        self.assertTrue(report.no_external_effect)
        self.assertEqual(report.case_count, 9)
        self.assertEqual(report.forest_expected_match_count, report.case_count)
        self.assertEqual(report.forest_expected_match_rate, 1.0)

    def test_fixed_legacy_baseline_remains_deliberately_shallow(self) -> None:
        report = run_shadow()
        # The baseline is intentionally not expected to detect the seeded
        # Forest-First route/teach-back/position/accusation failure classes.
        self.assertEqual(report.legacy_expected_match_count, report.case_count)
        self.assertEqual(report.legacy_detected_risk_cases, 0)
        self.assertGreater(report.forest_detected_risk_cases, report.legacy_detected_risk_cases)

    def test_case_ids_are_stable_and_unique(self) -> None:
        cases = build_shadow_cases()
        ids = [case.case_id for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "FF-SHADOW-001")
        self.assertEqual(ids[-1], "FF-SHADOW-009")


if __name__ == "__main__":
    unittest.main()
