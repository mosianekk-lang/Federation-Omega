from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Sequence


class HypothesisState(str, Enum):
    PROPOSED = "PROPOSED"
    FALSIFIED = "FALSIFIED"
    SUPPORTED = "SUPPORTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class StrategyOutcome:
    episode_id: str
    strategy_id: str
    objective_id: str
    verified_outcome: bool
    quality: float
    reliability: float
    latency_ms: float
    cost_units: float
    owner_minutes: float
    proof_refs: tuple[str, ...]
    observed: bool
    synthetic: bool = False


@dataclass(frozen=True)
class CausalHypothesis:
    hypothesis_id: str
    mechanism: str
    predicted_direction: str
    falsifier: str
    evidence_refs: tuple[str, ...] = ()
    state: HypothesisState = HypothesisState.PROPOSED


@dataclass(frozen=True)
class StrategyComparison:
    champion_id: str
    challenger_id: str
    quality_delta: float
    reliability_delta: float
    latency_delta_ms: float
    cost_delta: float
    owner_minutes_delta: float
    observed_pair: bool
    value_candidate: bool
    receipt: str


def _validate_outcome(outcome: StrategyOutcome) -> None:
    if not outcome.episode_id or not outcome.strategy_id or not outcome.objective_id:
        raise ValueError("episode, strategy and objective identities are required")
    if not 0.0 <= outcome.quality <= 1.0 or not 0.0 <= outcome.reliability <= 1.0:
        raise ValueError("quality and reliability must be within [0,1]")
    if outcome.latency_ms < 0 or outcome.cost_units < 0 or outcome.owner_minutes < 0:
        raise ValueError("metrics must be non-negative")
    if outcome.observed and outcome.synthetic:
        raise ValueError("synthetic outcome cannot be marked observed")
    if outcome.observed and not outcome.proof_refs:
        raise ValueError("observed outcome requires proof_refs")


def compare_strategies(champion: StrategyOutcome, challenger: StrategyOutcome) -> StrategyComparison:
    _validate_outcome(champion)
    _validate_outcome(challenger)
    if champion.episode_id != challenger.episode_id or champion.objective_id != challenger.objective_id:
        raise ValueError("strategy comparison requires matched episode and objective")
    if champion.strategy_id == challenger.strategy_id:
        raise ValueError("champion and challenger must differ")

    observed_pair = champion.observed and challenger.observed and not champion.synthetic and not challenger.synthetic
    quality_delta = challenger.quality - champion.quality
    reliability_delta = challenger.reliability - champion.reliability
    latency_delta = challenger.latency_ms - champion.latency_ms
    cost_delta = challenger.cost_units - champion.cost_units
    owner_delta = challenger.owner_minutes - champion.owner_minutes
    value_candidate = (
        observed_pair
        and champion.verified_outcome
        and challenger.verified_outcome
        and quality_delta >= 0
        and reliability_delta >= 0
        and owner_delta < 0
    )
    payload = {
        "episode_id": champion.episode_id,
        "objective_id": champion.objective_id,
        "champion_id": champion.strategy_id,
        "challenger_id": challenger.strategy_id,
        "quality_delta": round(quality_delta, 6),
        "reliability_delta": round(reliability_delta, 6),
        "latency_delta_ms": round(latency_delta, 6),
        "cost_delta": round(cost_delta, 6),
        "owner_minutes_delta": round(owner_delta, 6),
        "observed_pair": observed_pair,
        "value_candidate": value_candidate,
        "external_effect": False,
    }
    receipt = "sha256:" + sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return StrategyComparison(
        champion_id=champion.strategy_id,
        challenger_id=challenger.strategy_id,
        quality_delta=round(quality_delta, 6),
        reliability_delta=round(reliability_delta, 6),
        latency_delta_ms=round(latency_delta, 6),
        cost_delta=round(cost_delta, 6),
        owner_minutes_delta=round(owner_delta, 6),
        observed_pair=observed_pair,
        value_candidate=value_candidate,
        receipt=receipt,
    )


def update_hypothesis(
    hypothesis: CausalHypothesis,
    *,
    supporting_refs: Sequence[str] = (),
    falsifying_refs: Sequence[str] = (),
) -> CausalHypothesis:
    support = tuple(dict.fromkeys(ref for ref in supporting_refs if ref))
    falsifiers = tuple(dict.fromkeys(ref for ref in falsifying_refs if ref))
    if support and falsifiers:
        state = HypothesisState.UNRESOLVED
    elif falsifiers:
        state = HypothesisState.FALSIFIED
    elif support:
        state = HypothesisState.SUPPORTED
    else:
        state = HypothesisState.PROPOSED
    refs = tuple(sorted(set(hypothesis.evidence_refs) | set(support) | set(falsifiers)))
    return CausalHypothesis(
        hypothesis_id=hypothesis.hypothesis_id,
        mechanism=hypothesis.mechanism,
        predicted_direction=hypothesis.predicted_direction,
        falsifier=hypothesis.falsifier,
        evidence_refs=refs,
        state=state,
    )
