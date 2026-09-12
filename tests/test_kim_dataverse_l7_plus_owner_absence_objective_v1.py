from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_owner_absence_objective_v1 import owner_absence_objective


class KimDataverseLevel7PlusOwnerAbsenceObjectiveTests(unittest.TestCase):
    def test_same_value_scores_higher_with_less_owner_attention(self) -> None:
        low_burden = owner_absence_objective(verified_value=100, owner_minutes=2, avoidable_interruptions=0)
        high_burden = owner_absence_objective(verified_value=100, owner_minutes=20, avoidable_interruptions=2)
        self.assertGreater(low_burden, high_burden)

    def test_avoidable_interruptions_are_penalized(self) -> None:
        clean = owner_absence_objective(verified_value=100, owner_minutes=5, avoidable_interruptions=0)
        noisy = owner_absence_objective(verified_value=100, owner_minutes=5, avoidable_interruptions=2)
        self.assertGreater(clean, noisy)


if __name__ == "__main__":
    unittest.main()
