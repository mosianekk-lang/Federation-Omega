from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BacklogClass(str, Enum):
    AUTOPILOT = "AUTOPILOT"
    PROVIDER = "PROVIDER"
    VALUE = "VALUE"
    OWNER = "OWNER"


@dataclass(frozen=True)
class EmpiricalBacklogItem:
    item_id: str
    backlog_class: BacklogClass
    priority: int
    owner_action_required: bool
    evidence_target: str


def default_empirical_backlog() -> tuple[EmpiricalBacklogItem, ...]:
    return (
        EmpiricalBacklogItem("repair-current-phoenix", BacklogClass.AUTOPILOT, 100, False, "serving-main Phoenix green"),
        EmpiricalBacklogItem("observe-maintenance-self-resolution", BacklogClass.AUTOPILOT, 98, False, "10 real maintenance episodes"),
        EmpiricalBacklogItem("observe-recovery-self-resolution", BacklogClass.AUTOPILOT, 96, False, "10 real recovery episodes"),
        EmpiricalBacklogItem("prove-no-chat-resume", BacklogClass.AUTOPILOT, 95, False, "3 distinct cross-process resume receipts"),
        EmpiricalBacklogItem("collect-owner-value-pairs", BacklogClass.VALUE, 94, False, "30 prospective owner-value pairs"),
        EmpiricalBacklogItem("provider-wait-wake-handoff", BacklogClass.PROVIDER, 90, False, "provider-native wait/wake/handoff receipt"),
        EmpiricalBacklogItem("harden-google-wif", BacklogClass.OWNER, 80, True, "hardened exact WIF contract readback"),
        EmpiricalBacklogItem("cross-provider-counterfactual", BacklogClass.PROVIDER, 70, False, "paired provider-native counterfactual observations"),
    )
