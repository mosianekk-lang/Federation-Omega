"""Failure-derived mutation controls for Quant Evidence Fabric v3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class FailureSignature:
    parent_strategy_id: str
    evidence_ref: str
    failures: tuple[str, ...]


@dataclass(frozen=True)
class MutationProposal:
    parent_strategy_id: str
    mutation_id: str
    hypothesis: str
    changed_dimensions: tuple[str, ...]
    forbidden_unchanged_retry: bool = True


def propose_from_failure(signature: FailureSignature) -> MutationProposal:
    failures = set(signature.failures)
    dimensions: list[str] = []
    hypotheses: list[str] = []

    if "HOLDOUT_SAMPLE_TOO_SMALL" in failures:
        dimensions.append("entry_exit_frequency")
        hypotheses.append("increase legitimate signal opportunity without lowering evidence gates")
    if "MATERIAL_BENCHMARK_UNDERPERFORMANCE" in failures:
        dimensions.append("trend_participation")
        hypotheses.append("reduce unnecessary time out of sustained equity uptrends")
    if "CROSS_ASSET_GENERALISATION_FAILURE" in failures:
        dimensions.append("regime_adaptation")
        hypotheses.append("make risk filters adapt to asset volatility rather than one fixed regime")
    if not dimensions:
        dimensions.append("single_material_hypothesis")
        hypotheses.append("alter one causally justified dimension and retest identically")

    mutation_id = "FW-" + "-".join(dimensions)
    return MutationProposal(
        parent_strategy_id=signature.parent_strategy_id,
        mutation_id=mutation_id,
        hypothesis="; ".join(hypotheses),
        changed_dimensions=tuple(dimensions),
    )


def materially_changed(parent: Mapping[str, object], child: Mapping[str, object]) -> bool:
    return dict(parent) != dict(child)
