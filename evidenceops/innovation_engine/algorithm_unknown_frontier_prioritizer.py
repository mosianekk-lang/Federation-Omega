from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class UnknownFrontierPrioritizer:
    algorithm_id = "ALG-EOPS-UFP-001"
    name = "Unknown Frontier Prioritizer"

    def run(self, unknowns: Sequence[Mapping[str, Any]]) -> AlgorithmResult:
        ranked: list[dict[str, Any]] = []
        for index, item in enumerate(unknowns, start=1):
            unknown_id = text(item.get("unknown_id")) or f"UNK-{index:04d}"
            impact = clamp(number(item.get("impact"), 0.5))
            uncertainty = clamp(number(item.get("uncertainty"), 0.8))
            repetition = max(1.0, number(item.get("repetition"), 1.0))
            strategic = clamp(number(item.get("strategic_relevance"), 0.5))
            learnability = clamp(number(item.get("learnability"), 0.5))
            reuse = clamp(number(item.get("cross_domain_reuse"), 0.5))
            cost = max(0.05, clamp(number(item.get("investigation_cost"), 0.25)))
            risk = clamp(number(item.get("risk"), 0.2))
            burden = clamp(number(item.get("owner_burden"), 0.2))
            numerator = impact * uncertainty * repetition * (0.5 + strategic) * (0.5 + learnability) * (0.5 + reuse)
            denominator = 0.1 + cost + risk + burden
            score = numerator / denominator
            ranked.append(
                {
                    "unknown_id": unknown_id,
                    "question": text(item.get("question")) or text(item.get("description")),
                    "classification": text(item.get("classification")) or "KNOWN_UNKNOWN",
                    "score": round(score, 8),
                    "next_reversible_test": text(item.get("next_reversible_test")),
                    "evidence_refs": unique_text(sequence(item.get("evidence_refs"))),
                    "decision_sensitivity": clamp(number(item.get("decision_sensitivity"), impact)),
                }
            )
        ranked.sort(key=lambda row: (-row["score"], row["unknown_id"]))
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="FRONTIER_RANKED" if ranked else "NO_UNKNOWNS_SUPPLIED",
            maturity="TESTED_LOCAL",
            output={
                "ranked_unknowns": ranked,
                "highest_priority": ranked[0] if ranked else None,
                "unknown_count": len(ranked),
            },
            metrics={"unknown_count": float(len(ranked))},
        )
