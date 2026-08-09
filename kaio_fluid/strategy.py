from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyOption:
    name: str
    outcomes_by_world: dict[str, float]
    reversibility: float
    option_value: float


@dataclass(frozen=True)
class StrategyAssessment:
    name: str
    worst_case: float
    best_case: float
    mean: float
    max_regret: float
    reversibility: float
    option_value: float


class RobustStrategyEngine:
    """Select strategies under uncertainty without pretending precise probabilities."""

    def assess(self, options: tuple[StrategyOption, ...]) -> tuple[StrategyAssessment, ...]:
        if not options:
            return ()
        worlds = sorted({world for option in options for world in option.outcomes_by_world})
        best_by_world = {
            world: max(option.outcomes_by_world.get(world, float("-inf")) for option in options)
            for world in worlds
        }
        results = []
        for option in options:
            values = [option.outcomes_by_world.get(world, float("-inf")) for world in worlds]
            regrets = [best_by_world[world] - option.outcomes_by_world.get(world, float("-inf")) for world in worlds]
            finite_values = [v for v in values if v != float("-inf")]
            results.append(
                StrategyAssessment(
                    name=option.name,
                    worst_case=min(finite_values),
                    best_case=max(finite_values),
                    mean=sum(finite_values) / len(finite_values),
                    max_regret=max(regrets),
                    reversibility=max(0.0, min(1.0, option.reversibility)),
                    option_value=max(0.0, min(1.0, option.option_value)),
                )
            )
        return tuple(results)

    def minimax_regret(self, options: tuple[StrategyOption, ...]) -> StrategyAssessment | None:
        assessments = self.assess(options)
        if not assessments:
            return None
        return min(
            assessments,
            key=lambda a: (a.max_regret, -a.worst_case, -a.option_value, -a.reversibility, a.name),
        )

    def robust_choice(self, options: tuple[StrategyOption, ...]) -> StrategyAssessment | None:
        assessments = self.assess(options)
        if not assessments:
            return None
        return max(
            assessments,
            key=lambda a: (a.worst_case, a.option_value, a.reversibility, a.mean, a.name),
        )
