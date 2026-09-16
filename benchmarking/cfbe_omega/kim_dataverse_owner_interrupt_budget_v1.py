from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import OwnerBoundary


@dataclass(frozen=True)
class OwnerInterruption:
    interruption_id: str
    boundary: OwnerBoundary
    self_resolvable: bool
    material_choice: bool


@dataclass(frozen=True)
class InterruptionBudgetResult:
    total: int
    legitimate: int
    avoidable: int
    avoidable_ids: tuple[str, ...]
    rate: float
    within_budget: bool


def evaluate_interruption_budget(
    interruptions: Sequence[OwnerInterruption],
    *,
    maximum_avoidable_rate: float = 0.05,
) -> InterruptionBudgetResult:
    if not 0.0 <= maximum_avoidable_rate <= 1.0:
        raise ValueError("maximum_avoidable_rate must be within [0,1]")
    ids = [item.interruption_id for item in interruptions]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate interruption_id")
    avoidable = []
    legitimate = 0
    for item in interruptions:
        is_owner_boundary = item.boundary != OwnerBoundary.NONE
        if is_owner_boundary or item.material_choice:
            legitimate += 1
        elif item.self_resolvable:
            avoidable.append(item.interruption_id)
        else:
            avoidable.append(item.interruption_id)
    total = len(interruptions)
    rate = len(avoidable) / max(total, 1)
    return InterruptionBudgetResult(
        total=total,
        legitimate=legitimate,
        avoidable=len(avoidable),
        avoidable_ids=tuple(sorted(avoidable)),
        rate=round(rate, 6),
        within_budget=rate <= maximum_avoidable_rate,
    )
