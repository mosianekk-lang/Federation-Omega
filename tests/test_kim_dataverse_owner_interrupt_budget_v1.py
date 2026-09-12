from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import OwnerBoundary
from benchmarking.cfbe_omega.kim_dataverse_owner_interrupt_budget_v1 import OwnerInterruption, evaluate_interruption_budget


class KimDataverseOwnerInterruptionBudgetTests(unittest.TestCase):
    def test_self_resolvable_maintenance_interrupt_is_avoidable(self) -> None:
        result = evaluate_interruption_budget((OwnerInterruption("phoenix", OwnerBoundary.NONE, True, False),))
        self.assertEqual(1, result.avoidable)
        self.assertFalse(result.within_budget)

    def test_irreducible_authority_interrupt_is_legitimate(self) -> None:
        result = evaluate_interruption_budget((OwnerInterruption("wif", OwnerBoundary.AUTHORITY, False, True),))
        self.assertEqual(1, result.legitimate)
        self.assertEqual(0, result.avoidable)
        self.assertTrue(result.within_budget)

    def test_zero_interruptions_meets_zero_burden_target(self) -> None:
        result = evaluate_interruption_budget(())
        self.assertEqual(0.0, result.rate)
        self.assertTrue(result.within_budget)

    def test_duplicate_interruption_identity_fails_closed(self) -> None:
        item = OwnerInterruption("same", OwnerBoundary.NONE, True, False)
        with self.assertRaises(ValueError):
            evaluate_interruption_budget((item, item))


if __name__ == "__main__":
    unittest.main()
