from __future__ import annotations

from enum import IntEnum


class AutonomyMaturity(IntEnum):
    SHADOW = 0
    ADVISORY = 1
    BOUNDED_CONTROL = 2
    OPERATIONAL = 3
    SUSTAINED_VALUE = 4


def can_promote(current: AutonomyMaturity, target: AutonomyMaturity, *, evidence_complete: bool, authority_expansion: bool) -> bool:
    if authority_expansion:
        return False
    if target != current + 1:
        return False
    return evidence_complete
