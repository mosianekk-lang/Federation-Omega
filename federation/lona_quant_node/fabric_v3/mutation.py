"""Failure-derived mutation controls for Quant Evidence Fabric v3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class FailureSignature:
    parent_strategy_id: str
    evidence_ref: str
    failures: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class MutationProposal:
    parent_strategy_id: str
    mutation_id: str
    hypothesis: str
    changed_dimensions: tuple[str, ...]
    forbidden_unchanged_retry: bool = True
    material_change_required: bool = True
    auto_promote: bool = False
    external_effect: bool = False
    financial_effect: bool = False


_FAILURE_REPAIRS = {
    "HOLDOUT_SAMPLE_TOO_SMALL": (
        "entry_exit_frequency",
        "increase legitimate signal opportunity without lowering evidence gates",
    ),
    "MATERIAL_BENCHMARK_UNDERPERFORMANCE": (
        "trend_participation",
        "reduce unnecessary time out of sustained equity uptrends",
    ),
    "CROSS_ASSET_GENERALISATION_FAILURE": (
        "regime_adaptation",
        "make risk filters adapt to asset volatility rather than one fixed regime",
    ),
}

_DIAGNOSTIC_REPAIRS = {
    "CLOSE_BASED_STOP_EVALUATION": (
        "close_based_stop_semantics",
        "replace close-only stop triggering with bounded OHLC-aware semantics without lookahead",
    ),
    "CLOSE_BASED_STOP_SEMANTICS": (
        "close_based_stop_semantics",
        "replace close-only stop triggering with bounded OHLC-aware semantics without lookahead",
    ),
    "CROSS_ASSET_GENERALISATION_WEAKNESS": (
        "regime_adaptation",
        "make the next child prove behaviour across heterogeneous asset volatility regimes",
    ),
}


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def propose_from_failure(signature: FailureSignature) -> MutationProposal:
    if not signature.parent_strategy_id or not signature.evidence_ref:
        raise ValueError("parent_strategy_id and evidence_ref are required")

    dimensions: list[str] = []
    hypotheses: list[str] = []

    for failure in signature.failures:
        repair = _FAILURE_REPAIRS.get(failure)
        if repair is None:
            continue
        dimension, hypothesis = repair
        _append_unique(dimensions, dimension)
        _append_unique(hypotheses, hypothesis)

    for diagnostic in signature.diagnostics:
        repair = _DIAGNOSTIC_REPAIRS.get(diagnostic)
        if repair is None:
            continue
        dimension, hypothesis = repair
        _append_unique(dimensions, dimension)
        _append_unique(hypotheses, hypothesis)

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
