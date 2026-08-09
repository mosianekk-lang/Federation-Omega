from __future__ import annotations

from dataclasses import dataclass

from .abstraction import ProblemAbstraction, ProblemAbstractionEngine
from .compiler import CognitiveCompiler
from .core import FluidIntelligenceCore
from .discovery import DiscoveryEngine, RepresentationCandidate
from .immune import CognitiveImmuneSystem, ImmuneFinding
from .models import Hypothesis, ProblemContext, ReasoningPlan
from .morphogenesis import CognitiveArchitecture, CognitiveMorphogenesis
from .strategy import RobustStrategyEngine, StrategyAssessment, StrategyOption


@dataclass(frozen=True)
class CognitiveCycleResult:
    abstraction: ProblemAbstraction
    plan: ReasoningPlan
    hypotheses: tuple[Hypothesis, ...]
    reframes: tuple[str, ...]
    information_priorities: tuple[str, ...]
    representations: tuple[RepresentationCandidate, ...]
    architecture: CognitiveArchitecture
    immune_findings: tuple[ImmuneFinding, ...]
    strategy: StrategyAssessment | None
    evidence_resilience: dict[str, float | int]


class KaioFluidEngine:
    """Integrated A1-internal fluid intelligence cycle.

    This class coordinates reasoning only. It cannot promote truth, mutate source
    evidence, or perform consequential external actions.
    """

    def __init__(self) -> None:
        self.core = FluidIntelligenceCore()
        self.compiler = CognitiveCompiler(self.core)
        self.abstraction = ProblemAbstractionEngine()
        self.discovery = DiscoveryEngine()
        self.morphogenesis = CognitiveMorphogenesis()
        self.immune = CognitiveImmuneSystem()
        self.strategy = RobustStrategyEngine()

    def run(
        self,
        ctx: ProblemContext,
        *,
        actors: tuple[str, ...] = (),
        dependencies: tuple[str, ...] = (),
        unknowns: tuple[str, ...] = (),
        strategy_options: tuple[StrategyOption, ...] = (),
        temporal_density: float = 0.5,
        dependency_density: float = 0.5,
        causal_uncertainty: float | None = None,
        strategic_interaction: float = 0.5,
        element_structure: float = 0.5,
    ) -> CognitiveCycleResult:
        bounded = ctx.bounded()
        model = self.abstraction.abstract(
            bounded,
            actors=actors,
            dependencies=dependencies,
            unknowns=unknowns,
        )
        plan = self.compiler.compile(bounded)
        hypotheses = self.core.generate_hypotheses(bounded)
        reframes = self.core.reframe(bounded)
        priorities = self.core.information_gain_priority(bounded)
        representations = self.discovery.representation_tournament(
            temporal_density=temporal_density,
            dependency_density=dependency_density,
            causal_uncertainty=bounded.uncertainty if causal_uncertainty is None else causal_uncertainty,
            strategic_interaction=strategic_interaction,
            element_structure=element_structure,
        )
        architecture = self.morphogenesis.assemble(plan)
        immune_findings = self.immune.scan_evidence(bounded.evidence)
        strategy = self.strategy.robust_choice(strategy_options) if strategy_options else None
        resilience = self.core.evidence_resilience(bounded)

        return CognitiveCycleResult(
            abstraction=model,
            plan=plan,
            hypotheses=hypotheses,
            reframes=reframes,
            information_priorities=priorities,
            representations=representations,
            architecture=architecture,
            immune_findings=immune_findings,
            strategy=strategy,
            evidence_resilience=resilience,
        )
