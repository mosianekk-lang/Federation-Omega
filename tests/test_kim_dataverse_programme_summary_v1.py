from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_programme_summary_v1 import programme_summary


class KimDataverseProgrammeSummaryTests(unittest.TestCase):
    def test_current_source_programme_reaches_level6_candidate_not_operational_level7(self) -> None:
        summary = programme_summary()
        self.assertEqual(6, summary.highest_source_qualified_level)
        self.assertEqual(100.0, summary.architecture_score)
        self.assertEqual(100.0, summary.control_plane_score)
        self.assertFalse(summary.operational_level7_claim)
        self.assertLess(summary.empirical_score, 100.0)
        self.assertLess(summary.provider_score, 100.0)
        self.assertLess(summary.value_score, 100.0)


if __name__ == "__main__":
    unittest.main()
