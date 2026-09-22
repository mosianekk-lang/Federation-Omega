from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import Objective
from benchmarking.cfbe_omega.kim_dataverse_portfolio_unlock_v1 import rank_shared_capability_unlocks


class KimDataversePortfolioUnlockTests(unittest.TestCase):
    def test_shared_capability_ranks_above_single_objective_capability(self) -> None:
        ranked = rank_shared_capability_unlocks(
            (
                Objective("a", 5, 5, required_capabilities=("shared",)),
                Objective("b", 4, 4, required_capabilities=("shared",)),
                Objective("c", 5, 5, required_capabilities=("solo",)),
            )
        )
        self.assertEqual("shared", ranked[0].capability_id)
        self.assertEqual(2, ranked[0].objective_count)

    def test_duplicate_capability_within_objective_counts_once(self) -> None:
        ranked = rank_shared_capability_unlocks((Objective("a", 1, 1, required_capabilities=("x", "x")),))
        self.assertEqual(1, ranked[0].objective_count)

    def test_rank_is_deterministic(self) -> None:
        objectives = (Objective("a", 1, 1, required_capabilities=("x",)),)
        self.assertEqual(rank_shared_capability_unlocks(objectives), rank_shared_capability_unlocks(objectives))


if __name__ == "__main__":
    unittest.main()
