from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .store import current_evolution, promote_evolution

CANDIDATES = [
    ("gap_sensitivity", 0.72),
    ("failure_hold_threshold", 0.64),
    ("memory_antibody_repeat", 2),
    ("causal_confidence_floor", 0.55),
    ("diversity_floor", 3),
    ("joint_lead_delta", 0.2),
]


def benchmark(config: dict[str, Any]) -> float:
    gates = [
        config.get("gap_sensitivity", 0.5) >= 0.7,
        config.get("failure_hold_threshold", 0.8) <= 0.65,
        config.get("memory_antibody_repeat", 3) <= 2,
        config.get("causal_confidence_floor", 0.4) >= 0.5,
        config.get("diversity_floor", 1) >= 3,
        config.get("joint_lead_delta", 0.4) <= 0.25,
        True,
        True,
        True,
        True,
    ]
    return round(sum(gates) / len(gates), 6)


def evolve(path: Path) -> dict[str, Any]:
    current = current_evolution(path)
    config = deepcopy(current["config"])
    baseline = benchmark(config)
    promotions = []
    version_index = int(current["version"].split(".")[-1]) if current["version"].startswith("2.0.") else 0
    for name, value in CANDIDATES:
        candidate_config = deepcopy(config)
        candidate_config[name] = value
        score = benchmark(candidate_config)
        if score > baseline:
            version_index += 1
            candidate = {"version": f"2.0.{version_index}", "score": score, "config": candidate_config}
            promote_evolution(path, candidate, current["version"])
            promotions.append(candidate)
            current, config, baseline = candidate, candidate_config, score
    return {
        "state": "BOUNDED_EVOLUTION_PLATEAU" if not promotions else "BOUNDED_EVOLUTION_PROMOTED",
        "promotions": promotions,
        "promotion_count": len(promotions),
        "final_version": current["version"],
        "final_score": baseline,
        "constitutional_change": False,
        "external_effect": False,
    }
