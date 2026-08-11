from __future__ import annotations

from typing import Any

from .core import clamp


class Janus:
    name = "JANUS"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        decision = context.get("decision_passport", {})
        actual = float(context.get("observed_outcome_value", 0.0))
        selected = str(decision.get("selected_route", ""))
        feasible = [x for x in decision.get("alternatives", []) if x.get("feasible_at_time", True)]
        selected_row = next((x for x in feasible if x.get("id") == selected), {"expected_value": 0.0})
        best = max(feasible, key=lambda x: float(x.get("expected_value", 0.0)), default=selected_row)
        regret = max(0.0, float(best.get("expected_value", 0.0)) - actual)
        contributions = []
        for step in context.get("decision_steps", []):
            before = float(step.get("baseline", 0.0))
            after = float(step.get("observed_after", before))
            delta = after - before
            state = "HELPFUL" if delta > 0 else "HARMFUL" if delta < 0 else "REDUNDANT_OR_UNKNOWN"
            contributions.append({"step": step.get("id"), "causal_credit": state, "delta": round(delta, 6)})
        return {
            "system": self.name,
            "selected_route": selected,
            "best_feasible_route_at_time": best.get("id"),
            "regret": round(regret, 6),
            "causal_credit": contributions,
            "hindsight_information_excluded": True,
        }


class Symbiosis:
    name = "SYMBIOSIS"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        human = context.get("human_capability", {})
        machine = context.get("machine_capability", {})
        task = context.get("joint_task", {})
        value = task.get("type", "analysis")
        h = clamp(human.get(value, human.get("general", 0.5)))
        m = clamp(machine.get(value, machine.get("general", 0.5)))
        values_sensitive = bool(task.get("values_sensitive"))
        if values_sensitive:
            mode = "HUMAN_LEADS_AI_REFINES"
        elif m - h >= 0.2:
            mode = "AI_EXPLORES_HUMAN_SELECTS"
        elif h - m >= 0.2:
            mode = "HUMAN_LEADS_AI_CHECKS"
        else:
            mode = "JOINT_DELIBERATION"
        trust = 1 - abs(h - m) * 0.4
        return {
            "system": self.name,
            "allocation_mode": mode,
            "human_strength": round(h, 6),
            "machine_strength": round(m, 6),
            "joint_trust_calibration": round(clamp(trust), 6),
            "learning_objective": task.get("learning_objective", "IMPROVE_JOINT_DECISION_QUALITY"),
            "dependency_goal": "REDUCE_NOT_INCREASE",
        }
