from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from .core import clamp


class Polis:
    name = "POLIS"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        actors = context.get("actors", [])
        intervention = context.get("institutional_intervention", {})
        support, resistance = 0.0, 0.0
        responses = []
        for actor in actors:
            influence = float(actor.get("influence", 0.5))
            alignment = float(actor.get("alignment", 0.0))
            constraint = float(actor.get("constraint", 0.0))
            delta = float(intervention.get("alignment_delta", {}).get(actor.get("id"), 0.0))
            score = clamp((alignment + delta + 1) / 2) * influence * (1 - clamp(constraint))
            opposed = (1 - clamp((alignment + delta + 1) / 2)) * influence
            support += score
            resistance += opposed
            responses.append({"actor": actor.get("id"), "support": round(score, 6), "resistance": round(opposed, 6)})
        probability = support / max(0.000001, support + resistance)
        return {
            "system": self.name,
            "responses": responses,
            "coalition_support": round(support, 6),
            "coalition_resistance": round(resistance, 6),
            "institutional_success_probability": round(probability, 6),
            "simulation_only": True,
            "real_world_validation_required": True,
        }


class Chimera:
    name = "CHIMERA"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        edges = context.get("causal_edges", [])
        intervention = context.get("world_intervention", {})
        graph: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
        for edge in edges:
            graph[str(edge["cause"])].append((str(edge["effect"]), float(edge.get("strength", 0)), float(edge.get("confidence", 0))))
        start = str(intervention.get("target", ""))
        magnitude = float(intervention.get("magnitude", 0.0))
        effects = {start: magnitude}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for effect, strength, confidence in graph.get(current, []):
                propagated = effects[current] * strength * confidence
                previous = effects.get(effect, 0.0)
                if abs(propagated) > abs(previous):
                    effects[effect] = propagated
                    queue.append(effect)
        target = str(context.get("world_target_metric", "outcome"))
        baseline = float(context.get("world_baseline", 1.0))
        after = baseline + effects.get(target, 0.0)
        return {
            "system": self.name,
            "effects": {k: round(v, 6) for k, v in sorted(effects.items())},
            "counterfactual": {"baseline": baseline, "predicted_after": round(after, 6), "delta": round(after - baseline, 6)},
            "unresolved_confounders": list(context.get("unresolved_confounders", [])),
            "causality_state": "MODELLED_NOT_REAL_WORLD_PROVEN",
        }
