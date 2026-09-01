from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable, Mapping


class EvolutionError(ValueError):
    pass


@dataclass(frozen=True)
class TrialScore:
    candidate_id: str
    mission_id: str
    correctness: float
    proof_strength: float
    owner_burden: float
    cost: float
    latency_ms: int
    recovery_success: float

    @property
    def fitness(self) -> float:
        return (
            0.36 * self.correctness
            + 0.22 * self.proof_strength
            + 0.16 * self.recovery_success
            + 0.14 * (1.0 - self.owner_burden)
            + 0.07 * (1.0 - min(max(self.cost, 0.0), 1.0))
            + 0.05 * (1.0 - min(max(self.latency_ms, 0) / 100_000.0, 1.0))
        )


@dataclass(frozen=True)
class PromotionDecision:
    champion_id: str
    challenger_id: str
    decision: str
    champion_fitness: float
    challenger_fitness: float
    relative_gain: float
    common_missions: int
    reason: str


class ShadowEvolutionEngine:
    """Empirical champion/challenger selector with no execution authority.

    Candidates are compared only on missions both observed, preventing a challenger from
    winning by being evaluated on easier work. Promotion requires minimum evidence and a
    configurable gain floor.
    """

    def __init__(self) -> None:
        self._trials: list[TrialScore] = []

    def record(self, trial: TrialScore) -> None:
        for name, value in (
            ("correctness", trial.correctness),
            ("proof_strength", trial.proof_strength),
            ("owner_burden", trial.owner_burden),
            ("recovery_success", trial.recovery_success),
        ):
            if not 0.0 <= value <= 1.0:
                raise EvolutionError(f"{name} outside [0,1]")
        if not trial.candidate_id or not trial.mission_id:
            raise EvolutionError("candidate_id and mission_id are required")
        self._trials.append(trial)

    def compare(
        self,
        *,
        champion_id: str,
        challenger_id: str,
        min_common_missions: int = 20,
        min_relative_gain: float = 0.03,
    ) -> PromotionDecision:
        by_candidate: dict[str, dict[str, TrialScore]] = {}
        for trial in self._trials:
            by_candidate.setdefault(trial.candidate_id, {})[trial.mission_id] = trial
        champion = by_candidate.get(champion_id, {})
        challenger = by_candidate.get(challenger_id, {})
        common = sorted(set(champion) & set(challenger))
        if not common:
            return PromotionDecision(champion_id, challenger_id, "HOLD", 0.0, 0.0, 0.0, 0, "NO_COMMON_MISSIONS")
        champ_fit = mean(champion[mid].fitness for mid in common)
        chall_fit = mean(challenger[mid].fitness for mid in common)
        gain = (chall_fit - champ_fit) / max(abs(champ_fit), 1e-9)
        if len(common) < min_common_missions:
            decision, reason = "HOLD", "INSUFFICIENT_EVIDENCE"
        elif gain < min_relative_gain:
            decision, reason = "HOLD", "GAIN_BELOW_PROMOTION_FLOOR"
        else:
            decision, reason = "PROMOTE_CANDIDATE", "EMPIRICAL_GAIN_VERIFIED"
        return PromotionDecision(
            champion_id=champion_id,
            challenger_id=challenger_id,
            decision=decision,
            champion_fitness=champ_fit,
            challenger_fitness=chall_fit,
            relative_gain=gain,
            common_missions=len(common),
            reason=reason,
        )

    def candidate_rankings(self, *, min_missions: int = 1) -> tuple[tuple[str, float, int], ...]:
        grouped: dict[str, list[TrialScore]] = {}
        for trial in self._trials:
            grouped.setdefault(trial.candidate_id, []).append(trial)
        rows = [
            (candidate_id, mean(t.fitness for t in trials), len(trials))
            for candidate_id, trials in grouped.items()
            if len(trials) >= min_missions
        ]
        return tuple(sorted(rows, key=lambda x: (-x[1], -x[2], x[0])))


__all__ = ["EvolutionError", "PromotionDecision", "ShadowEvolutionEngine", "TrialScore"]
