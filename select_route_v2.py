from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


QUALIFIED_STATUS = "QUALIFIED_CURRENT_SCOPE"
_MINIMUM_METRICS = {"success_rate", "quality", "reliability", "proof", "availability"}
_MAXIMUM_METRICS = {"owner_burden", "cost", "latency", "error_rate", "risk"}


def _number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def normalized_goals(goals: Mapping[str, Any] | None) -> dict[str, Any]:
    """Canonicalise route goals so numeric equality never depends on Python type identity."""

    result: dict[str, Any] = {}
    for key, value in dict(goals or {}).items():
        if isinstance(value, bool):
            result[str(key)] = value
        elif isinstance(value, (int, float)):
            result[str(key)] = _number(value, field=str(key))
        else:
            result[str(key)] = value
    return result


def _eligible(route: Mapping[str, Any], goals: Mapping[str, Any]) -> bool:
    if str(route.get("status", "")) != QUALIFIED_STATUS:
        return False
    if bool(route.get("degraded", False)):
        return False
    metrics = route.get("metrics")
    if not isinstance(metrics, Mapping):
        return False

    for key, expected in goals.items():
        if key not in metrics:
            return False
        actual = metrics[key]
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            try:
                actual_number = _number(actual, field=f"metrics.{key}")
                expected_number = _number(expected, field=f"goals.{key}")
            except (TypeError, ValueError):
                return False
            if key in _MAXIMUM_METRICS:
                if actual_number > expected_number:
                    return False
            else:
                # Unknown numeric goals default to a floor. This is fail-closed
                # relative to a route promising at least the requested capability.
                if actual_number < expected_number:
                    return False
        elif actual != expected:
            return False
    return True


def _rank_key(route: Mapping[str, Any]) -> tuple[float, float, str]:
    metrics = route.get("metrics") if isinstance(route.get("metrics"), Mapping) else {}
    try:
        success = _number(metrics.get("success_rate", 0.0), field="metrics.success_rate")
    except (TypeError, ValueError):
        success = 0.0
    try:
        burden = _number(metrics.get("owner_burden", float("inf")), field="metrics.owner_burden")
    except (TypeError, ValueError):
        burden = float("inf")
    # max() prefers higher success, lower burden, then a stable route id.
    return success, -burden, str(route.get("route_id", ""))


def select_route(
    routes: Iterable[Mapping[str, Any]],
    *,
    goals: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the strongest current, non-degraded route satisfying every goal.

    Selection is deterministic and read-only. No route receives authority merely
    because it satisfies performance goals.
    """

    canonical_goals = normalized_goals(goals)
    candidates = [dict(route) for route in routes if _eligible(route, canonical_goals)]
    if not candidates:
        raise LookupError("NO_QUALIFIED_CURRENT_ROUTE_MEETS_GOALS")
    return max(candidates, key=_rank_key)


__all__ = ["QUALIFIED_STATUS", "normalized_goals", "select_route"]
