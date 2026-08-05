from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class EpistemicDebtPrioritizer:
    algorithm_id = "ALG-EOPS-EDP-001"
    name = "Epistemic Debt Prioritizer"

    debt_classes = {
        "UNTESTED_ASSUMPTION", "WEAK_EVIDENCE", "MISSING_BASELINE",
        "UNREPLICATED_FINDING", "STALE_STANDARD", "MEASUREMENT",
        "CAUSAL_UNCERTAINTY", "KNOWLEDGE_LINEAGE",
    }

    def run(self, debts: Sequence[Mapping[str, Any]]) -> AlgorithmResult:
        ranked: list[dict[str, Any]] = []
        violations: list[str] = []
        for index, debt in enumerate(debts, start=1):
            debt_id = text(debt.get("debt_id")) or f"DEBT-{index:04d}"
            debt_class = text(debt.get("debt_class")).upper()
            if debt_class not in self.debt_classes:
                violations.append(f"{debt_id}:UNSUPPORTED_EPISTEMIC_DEBT_CLASS")
                continue
            impact = clamp(number(debt.get("impact"), 0.5))
            uncertainty = clamp(number(debt.get("uncertainty"), 0.8))
            decision = clamp(number(debt.get("decision_sensitivity"), impact))
            repetition = max(1.0, number(debt.get("repetition"), 1.0))
            strategic = clamp(number(debt.get("strategic_relevance"), 0.5))
            reuse = clamp(number(debt.get("reuse_potential"), 0.5))
            cost = max(0.05, number(debt.get("closure_cost"), 0.25))
            burden = max(0.0, number(debt.get("owner_burden"), 0.1))
            score = (impact * uncertainty * decision * repetition * (0.5 + strategic) * (0.5 + reuse)) / (0.1 + cost + burden)
            ranked.append({
                "debt_id": debt_id,
                "debt_class": debt_class,
                "description": text(debt.get("description")),
                "score": round(score, 8),
                "closure_test": text(debt.get("closure_test")),
                "evidence_refs": unique_text(sequence(debt.get("evidence_refs"))),
            })
        ranked.sort(key=lambda row: (-row["score"], row["debt_id"]))
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="EPISTEMIC_DEBT_RANKED" if ranked else "NO_VALID_EPISTEMIC_DEBT",
            maturity="TESTED_LOCAL",
            output={"ranked_debts": ranked, "highest_priority": ranked[0] if ranked else None, "debt_count": len(ranked)},
            violations=tuple(violations),
            metrics={"debt_count": float(len(ranked))},
        )
