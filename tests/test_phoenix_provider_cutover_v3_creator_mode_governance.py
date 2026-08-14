from __future__ import annotations

import unittest

from evidenceops.lex_omega import (
    BurdenOwner,
    CREATOR_MODE_CONTRACT_VERSION,
    ForestFirstCreatorMode,
    WorkClass,
    WorkItem,
)


class CreatorModeGovernanceTests(unittest.TestCase):
    def test_contract_version_is_exposed(self) -> None:
        self.assertEqual(CREATOR_MODE_CONTRACT_VERSION, "1.0.1")

    def test_debug_burden_does_not_fall_back_to_kim_when_system_can_execute(self) -> None:
        report = ForestFirstCreatorMode().route((
            WorkItem("debug connector failure", WorkClass.SYSTEM_DEBUG),
            WorkItem("select fallback tool", WorkClass.TOOL_ROUTING),
            WorkItem("re-run verification", WorkClass.QA_VALIDATION),
            WorkItem("refresh continuity checkpoint", WorkClass.CONTINUITY),
        ))
        self.assertTrue(report.creator_focus_protected)
        self.assertEqual(report.user_required_count, 0)
        self.assertTrue(all(item.owner is BurdenOwner.SYSTEM for item in report.routed_items))

    def test_owner_reserved_decision_is_not_automated(self) -> None:
        report = ForestFirstCreatorMode().route((
            WorkItem("approve filing", WorkClass.CONSEQUENTIAL_APPROVAL, consequential=True),
        ))
        self.assertEqual(report.user_required_count, 1)
        self.assertIs(report.routed_items[0].owner, BurdenOwner.KIM)


if __name__ == "__main__":
    unittest.main()
