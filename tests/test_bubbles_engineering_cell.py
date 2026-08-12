from __future__ import annotations

import unittest

from bubbles.engineering_cell import WorkState
from bubbles.engineering_cell_loader import load_cell


class BubblesEngineeringCellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cell = load_cell()

    def test_preferred_sequence_is_exact(self) -> None:
        self.assertEqual(
            (
                "Bubbles",
                "Forge",
                "Sparks",
                "Pulse",
                "Patch",
                "Ledger",
                "Sentinel",
                "Bridge",
                "Scout",
                "Prism",
                "Beacon",
                "Showcase",
            ),
            self.cell.preferred_sequence(),
        )

    def test_every_role_has_real_work(self) -> None:
        report = self.cell.accountability_report()
        self.assertTrue(report["ready_for_operation"])
        self.assertEqual([], report["unassigned_roles"])
        self.assertEqual(12, report["role_count"])
        for role, count in report["workloads"].items():
            self.assertGreater(count, 0, role)

    def test_external_provider_effects_fail_closed(self) -> None:
        blocked = {item.work_id: item for item in self.cell.externally_blocked_work()}
        self.assertIn("BUB-SPARKS-CIOS-001", blocked)
        self.assertIn("BUB-SPARKS-ECERTIFY-001", blocked)
        self.assertEqual(WorkState.BLOCKED_EXTERNAL, blocked["BUB-SPARKS-ECERTIFY-001"].state)

    def test_internal_work_is_immediately_active(self) -> None:
        active = {item.work_id for item in self.cell.next_internal_work()}
        expected = {
            "BUB-CELL-ARCH-001",
            "BUB-FORGE-CIOS-001",
            "BUB-PULSE-CASEFORGE-001",
            "BUB-PATCH-IPEP-001",
            "BUB-LEDGER-PORTFOLIO-001",
            "BUB-SENTINEL-ECERTIFY-001",
            "BUB-BRIDGE-ARCHITRON-001",
            "BUB-SCOUT-CASEFORGE-001",
            "BUB-PRISM-IPEP-001",
            "BUB-BEACON-ECERTIFY-001",
            "BUB-SHOWCASE-PORTFOLIO-001",
            "BUB-PRISM-K10-001",
        }
        self.assertTrue(expected.issubset(active))

    def test_proof_gap_routing_is_specialised(self) -> None:
        self.assertEqual(("Forge", "Bubbles"), self.cell.route_gap("source"))
        self.assertEqual(("Pulse", "Forge"), self.cell.route_gap("tests"))
        self.assertEqual(("Ledger", "Sparks"), self.cell.route_gap("provider_readback"))
        self.assertEqual(("Patch", "Sparks"), self.cell.route_gap("observability"))
        self.assertEqual(("Prism", "Showcase", "Forge"), self.cell.route_gap("user_demo"))

    def test_active_does_not_claim_background_execution(self) -> None:
        item = self.cell.next_internal_work()[0]
        self.assertIn("does not imply asynchronous background execution", item.truth_boundary)


if __name__ == "__main__":
    unittest.main()
