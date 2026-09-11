from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Tuple


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    prior: float


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    expected_information_gain: float
    cost_units: float
    latency_ms: float
    risk: float
    discriminates: FrozenSet[str]
    reversible: bool = True
    authority_ok: bool = True
    safety_ok: bool = True


@dataclass(frozen=True)
class RankedExperiment:
    experiment: Experiment
    score: float


class ActiveExperimentPlanner:
    """Choose the cheapest safe experiment expected to reduce the most uncertainty.

    Authority/safety are hard gates. Ranking then rewards expected information
    gain and high-prior discriminating power while penalizing cost, latency,
    risk and irreversibility.
    """

    def __init__(
        self,
        hypotheses: Iterable[Hypothesis],
        experiments: Iterable[Experiment],
    ) -> None:
        self.hypotheses = tuple(hypotheses)
        self.experiments = tuple(experiments)
        total = sum(max(0.0, h.prior) for h in self.hypotheses)
        if total <= 0:
            raise ValueError("hypothesis priors must contain positive mass")
        self._priors = {
            h.hypothesis_id: max(0.0, h.prior) / total for h in self.hypotheses
        }

    def rank(self) -> Tuple[RankedExperiment, ...]:
        ranked = []
        for experiment in self.experiments:
            if not (experiment.authority_ok and experiment.safety_ok):
                continue
            prior_mass = sum(
                self._priors.get(hypothesis_id, 0.0)
                for hypothesis_id in experiment.discriminates
            )
            penalty = (
                max(0.001, experiment.cost_units)
                + max(0.0, experiment.latency_ms) / 10000.0
                + max(0.0, experiment.risk) * 2.0
                + (0.0 if experiment.reversible else 1.0)
            )
            score = (
                max(0.0, experiment.expected_information_gain)
                * (0.5 + prior_mass)
                / penalty
            )
            ranked.append(RankedExperiment(experiment, score))
        return tuple(
            sorted(
                ranked,
                key=lambda item: (-item.score, item.experiment.experiment_id),
            )
        )

    def best(self) -> Experiment:
        ranked = self.rank()
        if not ranked:
            raise RuntimeError("no authorized safe experiment available")
        return ranked[0].experiment
