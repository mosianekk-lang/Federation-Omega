from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, clamp, number,
    sequence, sha256, text, unique_text,
)

class InformationGainRouteSelector:
    algorithm_id = "ALG-EOPS-IGRS-001"
    name = "Information-Gain Route Selector"

    def run(self, experiments: Sequence[Mapping[str, Any]]) -> AlgorithmResult:
        ranked: list[dict[str, Any]] = []
        for index, experiment in enumerate(experiments, start=1):
            experiment_id = text(experiment.get("experiment_id")) or f"EXP-{index:04d}"
            information_gain = clamp(number(experiment.get("expected_information_gain"), 0.5))
            decision_sensitivity = clamp(number(experiment.get("decision_sensitivity"), 0.5))
            resolution_probability = clamp(number(experiment.get("resolution_probability"), 0.5))
            reversibility = clamp(number(experiment.get("reversibility"), 1.0))
            downstream_reuse = clamp(number(experiment.get("downstream_reuse"), 0.5))
            cost = max(0.01, number(experiment.get("cost"), 0.2))
            time = max(0.01, number(experiment.get("time"), 0.2))
            risk = max(0.01, number(experiment.get("risk"), 0.1))
            burden = max(0.01, number(experiment.get("owner_attention"), 0.1))
            score = (
                information_gain
                * decision_sensitivity
                * resolution_probability
                * reversibility
                * (0.5 + downstream_reuse)
            ) / (cost + time + risk + burden)
            ranked.append(
                {
                    "experiment_id": experiment_id,
                    "description": text(experiment.get("description")),
                    "score": round(score, 8),
                    "expected_information_gain": information_gain,
                    "reversibility": reversibility,
                    "stop_conditions": unique_text(sequence(experiment.get("stop_conditions"))),
                    "success_criteria": unique_text(sequence(experiment.get("success_criteria"))),
                    "authority": text(experiment.get("authority")) or AUTHORITY_CEILING,
                }
            )
        ranked.sort(key=lambda row: (-row["score"], row["experiment_id"]))
        selected = ranked[0] if ranked else None
        violations = []
        if selected and selected["authority"] not in {"A0_READ", AUTHORITY_CEILING}:
            violations.append("SELECTED_EXPERIMENT_EXCEEDS_A1_AUTHORITY")
            selected = None
        return AlgorithmResult(
            algorithm_id=self.algorithm_id,
            name=self.name,
            status="REVERSIBLE_EXPERIMENT_SELECTED" if selected else "NO_AUTHORISED_EXPERIMENT_SELECTED",
            maturity="TESTED_LOCAL",
            output={"ranked_experiments": ranked, "selected_experiment": selected},
            violations=tuple(violations),
            metrics={"experiment_count": float(len(ranked))},
        )
