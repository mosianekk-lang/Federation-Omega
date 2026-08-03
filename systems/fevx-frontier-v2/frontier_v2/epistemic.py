from __future__ import annotations

from collections import Counter
from typing import Any

from .core import clamp


class Noesis:
    name = "NOESIS"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        claims = set(context.get("claims", []))
        evidence = set(context.get("evidence", []))
        assumptions = list(context.get("assumptions", []))
        expected = set(context.get("expected_variables", []))
        observed = set(context.get("observed_variables", []))
        stakeholders = set(context.get("expected_stakeholders", []))
        represented = set(context.get("represented_stakeholders", []))
        gaps = []
        gaps += [{"type": "UNSUPPORTED_CLAIM", "item": x} for x in sorted(claims - evidence)]
        gaps += [{"type": "MISSING_VARIABLE", "item": x} for x in sorted(expected - observed)]
        gaps += [{"type": "UNREPRESENTED_STAKEHOLDER", "item": x} for x in sorted(stakeholders - represented)]
        gaps += [{"type": "UNTESTED_ASSUMPTION", "item": x.get("item", str(x))} for x in assumptions if not x.get("tested")]
        decision_sensitive = [g for g in gaps if g.get("item") not in set(context.get("low_value_gaps", []))]
        experiments = [
            {"experiment": f"PROBE:{g['type']}:{g['item']}", "reversible": True, "external_effect": False}
            for g in decision_sensitive[:5]
        ]
        coverage = 1.0 - (len(decision_sensitive) / max(1, len(claims) + len(expected) + len(stakeholders)))
        return {
            "system": self.name,
            "gaps": gaps,
            "decision_sensitive_gaps": decision_sensitive,
            "experiments": experiments,
            "epistemic_coverage": round(clamp(coverage), 6),
        }


class Lucid:
    name = "LUCID"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        task = context.get("task_type", "unknown")
        history = [x for x in context.get("competence_history", []) if x.get("task_type") == task]
        if history:
            successes = sum(bool(x.get("success")) for x in history)
            calibration = sum(float(x.get("calibration", 0.5)) for x in history) / len(history)
            competence = 0.65 * successes / len(history) + 0.35 * calibration
        else:
            competence = float(context.get("prior_competence", 0.45))
        missing = len(context.get("missing_inputs", []))
        shift = float(context.get("distribution_shift", 0.0))
        failure_probability = clamp(1 - competence + 0.08 * missing + 0.25 * shift)
        if failure_probability >= 0.65:
            route = "HOLD_AND_ACQUIRE_EVIDENCE"
        elif failure_probability >= 0.35:
            route = "ACT_WITH_INDEPENDENT_VERIFIER"
        else:
            route = "ACT_WITH_READBACK"
        modes = Counter(x.get("failure_mode", "UNKNOWN") for x in history if not x.get("success"))
        return {
            "system": self.name,
            "task_type": task,
            "competence": round(clamp(competence), 6),
            "failure_probability": round(failure_probability, 6),
            "likely_failure_mode": modes.most_common(1)[0][0] if modes else "INSUFFICIENT_HISTORY",
            "route": route,
            "authority_ceiling": "A1_INTERNAL",
        }
