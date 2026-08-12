from __future__ import annotations

import unittest

from bubbles.engineering_cell import WorkState
from bubbles.engineering_cell_loader import load_cell


class BubblesEngineeringCellAdmissionTests(unittest.TestCase):
    def test_full_cell_is_loaded_and_every_role_has_work(self) -> None:
        cell = load_cell()
        report = cell.accountability_report()
        self.assertTrue(report["ready_for_operation"])
        self.assertEqual(12, report["role_count"])
        self.assertEqual([], report["unassigned_roles"])
        self.assertEqual("Bubbles", report["preferred_sequence"][0])
        self.assertEqual("Showcase", report["preferred_sequence"][-1])

    def test_provider_effects_remain_fail_closed(self) -> None:
        cell = load_cell()
        blocked = {item.work_id: item for item in cell.externally_blocked_work()}
        self.assertEqual(WorkState.BLOCKED_EXTERNAL, blocked["BUB-SPARKS-CIOS-001"].state)
        self.assertEqual(WorkState.BLOCKED_EXTERNAL, blocked["BUB-SPARKS-ECERTIFY-001"].state)
        self.assertGreaterEqual(len(cell.next_internal_work()), 10)


if __name__ == "__main__":
    unittest.main()
