from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.cycle_preflight_v1 import load_cycle_preflight


class CFBECyclePreflightTests(unittest.TestCase):
    def test_contract_is_freshness_first_and_architecture_last(self) -> None:
        contract = load_cycle_preflight()
        order = contract["preflight_order"]
        gates = contract["gates"]
        self.assertEqual(order[0], "FRESH_READ_CURRENT_MAIN")
        self.assertIn("READ_CURRENT_TERMINAL_STATUS", order)
        self.assertIn("REPAIR_CURRENT_RED_TERMINAL_STATE_IF_SAFE", order)
        self.assertEqual(order[-1], "ONLY_THEN_CONSIDER_NEW_ARCHITECTURE")
        self.assertTrue(gates["critical_current_regression_blocks_new_architecture"])
        self.assertTrue(gates["historical_green_tranche_is_not_current_terminal_truth"])
        self.assertTrue(gates["pr_open_requires_stable_self_reviewed_branch"])


if __name__ == "__main__":
    unittest.main()
