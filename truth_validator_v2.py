from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class TruthVerdict:
    passed: bool
    reasons: tuple[str, ...]


class TruthValidator:
    """Fail-closed bounded runtime truth validator.

    Duration is a minimum floor unless the observation explicitly declares an
    exact-duration contract. Provider/readback, scope, duplicate suppression and
    fallback protection remain independent gates.
    """

    def validate(
        self,
        *,
        observation: Mapping[str, Any],
        scope_ok: bool,
        readback_ok: bool,
        fresh_canary_ok: bool,
        fallback_protected: bool,
    ) -> TruthVerdict:
        reasons: list[str] = []

        if not scope_ok:
            reasons.append("scope_not_verified")
        if not readback_ok:
            reasons.append("readback_not_verified")
        if not fresh_canary_ok:
            reasons.append("fresh_canary_not_verified")
        if not fallback_protected:
            reasons.append("fallback_not_protected")
        if not bool(observation.get("current_identity_bound", False)):
            reasons.append("current_identity_not_bound")
        if not bool(observation.get("no_duplicate_execution", False)):
            reasons.append("duplicate_execution_not_excluded")
        if not bool(observation.get("duplicate_suppression_current", False)):
            reasons.append("duplicate_suppression_not_current")

        for field, reason in (
            ("bypass_attempts", "bypass_attempts_present"),
            ("wrong_scope_effects", "wrong_scope_effects_present"),
            ("owner_burden_events", "owner_burden_increase_present"),
            ("compatibility_failures", "compatibility_failures_present"),
        ):
            try:
                value = int(observation.get(field, 0))
            except (TypeError, ValueError):
                reasons.append(f"{field}_invalid")
            else:
                if value != 0:
                    reasons.append(reason)

        try:
            fresh_count = int(observation.get("fresh_canary_count", 0))
        except (TypeError, ValueError):
            reasons.append("fresh_canary_count_invalid")
        else:
            if fresh_count < 1:
                reasons.append("fresh_canary_count_insufficient")

        try:
            duration = float(observation.get("duration_minutes", 0.0))
            required = float(observation.get("required_duration_minutes", 0.0))
        except (TypeError, ValueError):
            reasons.append("duration_invalid")
        else:
            if duration < 0 or required < 0:
                reasons.append("duration_invalid")
            elif bool(observation.get("duration_must_equal_required", False)):
                if duration != required:
                    reasons.append("duration_exact_violation")
            elif duration < required:
                reasons.append("duration_floor_not_met")

        return TruthVerdict(passed=not reasons, reasons=tuple(reasons))


__all__ = ["TruthVerdict", "TruthValidator"]
