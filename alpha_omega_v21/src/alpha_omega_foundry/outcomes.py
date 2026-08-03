from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import datetime
import hashlib
import json


@dataclass
class OutcomeCostGovernor:
    workspace: Path

    def __post_init__(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.ledger = self.workspace / "outcome_cost_ledger.jsonl"

    def verify_outcomes(self, expected: dict, actual: dict) -> dict:
        measures = {}
        for name, target in expected.items():
            observed = actual.get(name)
            if isinstance(target, (int, float)) and isinstance(observed, (int, float)):
                achieved = observed >= target
                ratio = 1.0 if target == 0 else min(observed / target, 1.0)
            else:
                achieved = observed == target
                ratio = 1.0 if achieved else 0.0
            measures[name] = {
                "target": target,
                "observed": observed,
                "achieved": achieved,
                "score": round(ratio, 4),
            }
        score = round(sum(row["score"] for row in measures.values()) / max(len(measures), 1), 4)
        return {"pass": score >= 0.8, "score": score, "measures": measures}

    def goodhart_check(self, primary: dict, safeguards: dict) -> dict:
        primary_pass = all(bool(value) for value in primary.values())
        failed_safeguards = sorted(name for name, value in safeguards.items() if not bool(value))
        return {
            "primary_pass": primary_pass,
            "failed_safeguards": failed_safeguards,
            "gaming_risk": primary_pass and bool(failed_safeguards),
            "pass": primary_pass and not failed_safeguards,
        }

    def evaluate_cost(self, costs: dict, budget: dict) -> dict:
        rows = {}
        over = []
        for name, limit in budget.items():
            actual = float(costs.get(name, 0.0))
            limit = float(limit)
            within = actual <= limit
            rows[name] = {"actual": actual, "limit": limit, "within_budget": within}
            if not within:
                over.append(name)
        return {"pass": not over, "over_budget": sorted(over), "dimensions": rows}

    def value_score(self, outcome_score: float, reliability: float, cost_efficiency: float, risk: float) -> float:
        score = outcome_score * 0.4 + reliability * 0.25 + cost_efficiency * 0.25 + (1.0 - risk) * 0.1
        return round(max(0.0, min(score, 1.0)), 4)

    def decide(self, outcome: dict, goodhart: dict, cost: dict, value_score: float) -> dict:
        if goodhart["gaming_risk"]:
            action = "HOLD_AND_REDESIGN_MEASURES"
        elif not cost["pass"]:
            action = "OPTIMISE_COST_AND_RETEST"
        elif not outcome["pass"]:
            action = "IMPROVE_AND_RETEST"
        elif value_score < 0.35:
            action = "RETIRE_OR_REPLACE"
        elif value_score < 0.7:
            action = "CONTINUE_WITH_IMPROVEMENT"
        else:
            action = "PROMOTE_AND_MAINTAIN"
        return {"action": action, "automatic": action != "HOLD_AND_REDESIGN_MEASURES"}

    def record(self, system_id: str, outcome: dict, goodhart: dict, cost: dict, value_score: float, decision: dict) -> dict:
        row = {
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            "system_id": system_id,
            "outcome": outcome,
            "goodhart": goodhart,
            "cost": cost,
            "value_score": value_score,
            "decision": decision,
        }
        row["receipt_id"] = "RCP-OC-" + hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12]
        with self.ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        return row
