from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_autonomy_debt_repair_v1 import (
    DebtRepairAction,
    highest_priority_repair,
    plan_autonomy_debt_repairs,
)
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import AutonomyDebt


class KimDataverseAutonomyDebtRepairTests(unittest.TestCase):
    def test_chat_dependency_prioritizes_persistent_carrier(self) -> None:
        repair = highest_priority_repair(AutonomyDebt(chat_session_dependencies=1, owner_continuations=2))
        self.assertEqual(DebtRepairAction.ADD_PERSISTENT_CARRIER, repair.action)

    def test_unrelated_gate_stall_isolated_before_manual_trigger_fix(self) -> None:
        repairs = plan_autonomy_debt_repairs(AutonomyDebt(unrelated_gate_stalls=1, owner_continuations=1))
        self.assertEqual(DebtRepairAction.ISOLATE_BLOCKED_LANE, repairs[0].action)

    def test_owner_repair_prompt_creates_maintenance_route(self) -> None:
        actions = {repair.action for repair in plan_autonomy_debt_repairs(AutonomyDebt(owner_repair_prompts=1))}
        self.assertIn(DebtRepairAction.ADD_MAINTENANCE_ROUTE, actions)

    def test_rediscovered_failure_creates_failure_memory_repair(self) -> None:
        actions = {repair.action for repair in plan_autonomy_debt_repairs(AutonomyDebt(rediscovered_failures=1))}
        self.assertIn(DebtRepairAction.ADD_FAILURE_MEMORY, actions)

    def test_no_debt_returns_noop(self) -> None:
        repair = highest_priority_repair(AutonomyDebt())
        self.assertEqual(DebtRepairAction.NONE, repair.action)


if __name__ == "__main__":
    unittest.main()
