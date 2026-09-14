from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import Objective


@dataclass(frozen=True)
class CapabilityUnlock:
    capability_id: str
    objective_count: int
    total_value_weight: float
    total_urgency_weight: float
    leverage_score: float


def rank_shared_capability_unlocks(objectives: Sequence[Objective]) -> tuple[CapabilityUnlock, ...]:
    buckets: dict[str, list[Objective]] = {}
    for objective in objectives:
        for capability in set(objective.required_capabilities):
            buckets.setdefault(capability, []).append(objective)
    unlocks = []
    for capability_id, linked in buckets.items():
        count = len(linked)
        value = sum(item.value_weight for item in linked)
        urgency = sum(item.urgency_weight for item in linked)
        leverage = count * 0.4 + value * 0.4 + urgency * 0.2
        unlocks.append(
            CapabilityUnlock(
                capability_id=capability_id,
                objective_count=count,
                total_value_weight=round(value, 6),
                total_urgency_weight=round(urgency, 6),
                leverage_score=round(leverage, 6),
            )
        )
    return tuple(sorted(unlocks, key=lambda item: (-item.leverage_score, item.capability_id)))
