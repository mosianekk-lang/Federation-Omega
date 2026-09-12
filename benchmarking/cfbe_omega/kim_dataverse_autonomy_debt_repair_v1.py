from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import AutonomyDebt


class DebtRepairAction(str, Enum):
    NONE = "NONE"
    AUTOMATE_TRIGGER = "AUTOMATE_TRIGGER"
    ADD_PERSISTENT_CARRIER = "ADD_PERSISTENT_CARRIER"
    ADD_MAINTENANCE_ROUTE = "ADD_MAINTENANCE_ROUTE"
    ADD_FAILURE_MEMORY = "ADD_FAILURE_MEMORY"
    ISOLATE_BLOCKED_LANE = "ISOLATE_BLOCKED_LANE"
    ARCHITECTURE_REVIEW = "ARCHITECTURE_REVIEW"


@dataclass(frozen=True)
class DebtRepair:
    action: DebtRepairAction
    priority: int
    rationale: str


def plan_autonomy_debt_repairs(debt: AutonomyDebt) -> tuple[DebtRepair, ...]:
    repairs: list[DebtRepair] = []
    if debt.owner_continuations or debt.retriggered_stalls:
        repairs.append(DebtRepair(DebtRepairAction.AUTOMATE_TRIGGER, 90, "owner is acting as continuation scheduler"))
    if debt.chat_session_dependencies:
        repairs.append(DebtRepair(DebtRepairAction.ADD_PERSISTENT_CARRIER, 100, "work depends on chat/session continuity"))
    if debt.owner_repair_prompts or debt.owner_resolved_internal_drift:
        repairs.append(DebtRepair(DebtRepairAction.ADD_MAINTENANCE_ROUTE, 95, "self-resolvable maintenance reached owner"))
    if debt.rediscovered_failures:
        repairs.append(DebtRepair(DebtRepairAction.ADD_FAILURE_MEMORY, 85, "known failure was rediscovered"))
    if debt.unrelated_gate_stalls:
        repairs.append(DebtRepair(DebtRepairAction.ISOLATE_BLOCKED_LANE, 98, "independent work was frozen by unrelated gate"))
    if debt.repeated_automatable_actions or debt.restated_directives:
        repairs.append(DebtRepair(DebtRepairAction.ARCHITECTURE_REVIEW, 80, "repeated manual behavior indicates automation debt"))
    if not repairs:
        repairs.append(DebtRepair(DebtRepairAction.NONE, 0, "no autonomy debt detected"))
    return tuple(sorted(repairs, key=lambda item: (-item.priority, item.action.value)))


def highest_priority_repair(debt: AutonomyDebt) -> DebtRepair:
    return plan_autonomy_debt_repairs(debt)[0]
