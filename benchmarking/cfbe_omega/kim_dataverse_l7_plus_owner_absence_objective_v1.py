from __future__ import annotations


def owner_absence_objective(*, verified_value: float, owner_minutes: float, avoidable_interruptions: int) -> float:
    if verified_value < 0 or owner_minutes < 0 or avoidable_interruptions < 0:
        raise ValueError("inputs must be non-negative")
    denominator = max(1.0, owner_minutes + avoidable_interruptions * 5.0)
    return round(verified_value / denominator, 6)
