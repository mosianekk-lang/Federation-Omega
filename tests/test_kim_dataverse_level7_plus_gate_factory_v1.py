from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_completion_matrix_v1 import compile_completion_matrix
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_gate_factory_v1 import current_level7_plus_gates


class KimDataverseLevel7PlusGateFactoryTests(unittest.TestCase):
    def test_current_source_closes_level5_and_level6_source_gates(self) -> None:
        by_id = {gate.gate_id: gate for gate in current_level7_plus_gates()}
        self.assertTrue(by_id["level5-source"].satisfied)
        self.assertTrue(by_id["level6-source"].satisfied)

    def test_empirical_level7_and_wif_gates_remain_open(self) -> None:
        by_id = {gate.gate_id: gate for gate in current_level7_plus_gates()}
        self.assertFalse(by_id["persistent-no-chat"].satisfied)
        self.assertFalse(by_id["verified-value-retention"].satisfied)
        self.assertFalse(by_id["google-wif-authority"].satisfied)

    def test_current_completion_matrix_caps_at_level6_and_separates_owner_gate(self) -> None:
        matrix = compile_completion_matrix(current_level7_plus_gates())
        self.assertEqual(6, matrix.highest_unblocked_level)
        self.assertIn("google-wif-authority", matrix.owner_gates)
        self.assertIn("persistent-no-chat", matrix.safe_autopilot_gates)


if __name__ == "__main__":
    unittest.main()
