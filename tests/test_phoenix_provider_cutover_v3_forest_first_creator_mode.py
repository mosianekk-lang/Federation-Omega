from __future__ import annotations

import unittest

from evidenceops.lex_omega.forest_first_creator_mode import (
    BurdenOwner,
    ForestFirstCreatorMode,
    WorkClass,
    WorkItem,
)


class ForestFirstCreatorModeTests(unittest.TestCase):
    def test_debugging_and_tool_routing_are_absorbed_by_system(self) -> None:
        report = ForestFirstCreatorMode().route((
            WorkItem("debug failed bridge", WorkClass.SYSTEM_DEBUG),
            WorkItem("select best connector", WorkClass.TOOL_ROUTING),
            WorkItem("verify readback", WorkClass.QA_VALIDATION),
        ))
        self.assertTrue(report.creator_focus_protected)
        self.assertEqual(report.system_absorbed_count, 3)
        self.assertEqual(report.user_required_count, 0)
        self.assertTrue(all(item.owner is BurdenOwner.SYSTEM for item in report.routed_items))

    def test_consequential_approval_stays_with_kim(self) -> None:
        report = ForestFirstCreatorMode().route((
            WorkItem("approve legal filing", WorkClass.CONSEQUENTIAL_APPROVAL, consequential=True),
        ))
        self.assertEqual(report.user_required_count, 1)
        self.assertIs(report.routed_items[0].owner, BurdenOwner.KIM)

    def test_unique_lived_fact_stays_with_kim(self) -> None:
        report = ForestFirstCreatorMode().route((
            WorkItem(
                "confirm what was said in an undocumented meeting",
                WorkClass.FACT_ONLY_USER_KNOWS,
                user_has_unique_information=True,
            ),
        ))
        self.assertEqual(report.user_required_count, 1)
        self.assertIs(report.routed_items[0].owner, BurdenOwner.KIM)

    def test_unavailable_system_route_is_shared_not_dumped_on_user(self) -> None:
        report = ForestFirstCreatorMode().route((
            WorkItem("provider-specific operation unavailable", WorkClass.RESEARCH_RETRIEVAL, system_can_execute=False),
        ))
        self.assertEqual(report.shared_count, 1)
        self.assertIs(report.routed_items[0].owner, BurdenOwner.SHARED)


if __name__ == "__main__":
    unittest.main()
