from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_completion_matrix_v1 import CompletionGate, GateClass, compile_completion_matrix


class KimDataverseLevel7PlusCompletionMatrixTests(unittest.TestCase):
    def test_autopilot_and_owner_gates_are_separated(self) -> None:
        matrix = compile_completion_matrix(
            (
                CompletionGate("phoenix-repair", GateClass.SOURCE, False, 5),
                CompletionGate("wif-authority", GateClass.OWNER, False, 7, authority_required=True),
                CompletionGate("owner-value", GateClass.VALUE, False, 7),
            )
        )
        self.assertEqual(("wif-authority",), matrix.owner_gates)
        self.assertEqual(("owner-value", "phoenix-repair"), matrix.safe_autopilot_gates)

    def test_open_level5_gate_caps_highest_unblocked_level_at4(self) -> None:
        matrix = compile_completion_matrix((CompletionGate("g", GateClass.SOURCE, False, 5),))
        self.assertEqual(4, matrix.highest_unblocked_level)

    def test_all_gates_satisfied_reaches_level8_source_completion_matrix(self) -> None:
        matrix = compile_completion_matrix((CompletionGate("g", GateClass.SOURCE, True, 5),))
        self.assertEqual(8, matrix.highest_unblocked_level)
        self.assertEqual((), matrix.open_gates)

    def test_duplicate_gate_id_fails_closed(self) -> None:
        gate = CompletionGate("same", GateClass.SOURCE, False, 5)
        with self.assertRaises(ValueError):
            compile_completion_matrix((gate, gate))


if __name__ == "__main__":
    unittest.main()
