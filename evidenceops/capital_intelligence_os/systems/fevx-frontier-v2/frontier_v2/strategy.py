from __future__ import annotations

from collections import defaultdict
from typing import Any

from .core import clamp, digest


class Argonaut:
    name = "ARGONAUT"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        ranked = []
        for route in context.get("strategy_routes", []):
            expected = float(route.get("value", 0)) * clamp(route.get("probability", 0))
            option = float(route.get("option_value", 0)) + float(route.get("information_gain", 0))
            burden = float(route.get("cost", 0)) + float(route.get("risk", 0)) + float(route.get("owner_attention", 0))
            reversibility = clamp(route.get("reversibility", 0.5))
            score = expected + option * reversibility - burden
            ranked.append({**route, "score": round(score, 6)})
        ranked.sort(key=lambda x: (-x["score"], str(x.get("id"))))
        selected = ranked[:3]
        roles = ["PRIMARY", "HEDGE", "PROBE"]
        portfolio = [{"role": roles[i], **row} for i, row in enumerate(selected)]
        return {"system": self.name, "portfolio": portfolio, "preserved_options": len(ranked), "premature_lock_in": False}


class Polylogue:
    name = "POLYLOGUE"

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        proposals = list(context.get("deliberation_proposals", []))
        families: dict[str, list[dict[str, Any]]] = defaultdict(list)
        weighted, total = 0.0, 0.0
        for proposal in proposals:
            fingerprint = digest({"position": proposal.get("position"), "assumptions": proposal.get("assumptions", [])})
            families[fingerprint].append(proposal)
            reputation = clamp(proposal.get("reputation", 0.5))
            confidence = clamp(proposal.get("confidence", 0.5))
            weight = max(0.01, reputation * confidence)
            weighted += float(proposal.get("probability", 0.5)) * weight
            total += weight
        duplicates = sum(max(0, len(rows) - 1) for rows in families.values())
        independent = max(0, len(proposals) - duplicates)
        aggregate = weighted / total if total else 0.5
        minority = [p for p in proposals if abs(float(p.get("probability", 0.5)) - aggregate) >= 0.25]
        return {
            "system": self.name,
            "aggregate_probability": round(aggregate, 6),
            "independent_viewpoints": independent,
            "copied_reasoning_count": duplicates,
            "minority_hypotheses_preserved": len(minority),
            "diversity_sufficient": independent >= min(3, len(proposals)),
        }
