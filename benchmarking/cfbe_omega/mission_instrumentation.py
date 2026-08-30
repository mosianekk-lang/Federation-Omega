"""Additive CFBE instrumentation over existing SOVARA/Formation telemetry.

This module does not replace OpenTelemetry or SOVARA MCF. It adds the three
measurement facts that the existing mission telemetry does not consistently emit
and validates the existing economic/owner/rollback fields needed by Evidence
Autopilot.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


REQUIRED_BASE_KEYS = frozenset(
    {
        "sovara.mission.value",
        "sovara.mission.cost",
        "sovara.mission.risk",
        "sovara.owner.intervention_seconds",
        "sovara.rollback.available",
    }
)


def _bounded_non_negative(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"MISSION_INSTRUMENTATION_NUMERIC_REQUIRED:{name}") from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"MISSION_INSTRUMENTATION_NON_NEGATIVE_FINITE_REQUIRED:{name}")
    return number


def enrich_mission_telemetry(
    base_attributes: Mapping[str, Any],
    *,
    information_questions_resolved: float,
    proof_axes_gained: float,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Return a new measurement-ready telemetry mapping; never mutate the input."""
    missing = sorted(REQUIRED_BASE_KEYS - set(base_attributes))
    if missing:
        raise ValueError("MISSION_INSTRUMENTATION_BASE_FIELDS_MISSING:" + ",".join(missing))
    result = dict(base_attributes)
    result["cfbe.information.questions_resolved"] = _bounded_non_negative(
        information_questions_resolved, "information_questions_resolved"
    )
    result["cfbe.proof.axes_gained"] = _bounded_non_negative(
        proof_axes_gained, "proof_axes_gained"
    )
    result["sovara.mission.elapsed_seconds"] = _bounded_non_negative(
        elapsed_seconds, "elapsed_seconds"
    )
    if not isinstance(result["sovara.rollback.available"], bool):
        raise ValueError("MISSION_INSTRUMENTATION_ROLLBACK_BOOLEAN_REQUIRED")
    for key in (
        "sovara.mission.value",
        "sovara.mission.cost",
        "sovara.mission.risk",
        "sovara.owner.intervention_seconds",
    ):
        _bounded_non_negative(result[key], key)
    return result
