from __future__ import annotations

from dataclasses import dataclass

from .models import CognitiveMode, ReasoningPlan


@dataclass(frozen=True)
class TemporarySpecialist:
    name: str
    competencies: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    external_effect: bool = False


@dataclass(frozen=True)
class CognitiveArchitecture:
    mode: CognitiveMode
    topology: str
    specialists: tuple[TemporarySpecialist, ...]
    dissolve_after_task: bool = True


class CognitiveMorphogenesis:
    """Compile a temporary team topology from a bounded reasoning plan."""

    def assemble(self, plan: ReasoningPlan) -> CognitiveArchitecture:
        specialists: list[TemporarySpecialist] = []
        for name in plan.specialists:
            competencies = self._competencies_for(name)
            specialists.append(TemporarySpecialist(name=name, competencies=competencies))

        if plan.mode in {CognitiveMode.DEEP_SYNTHESIS, CognitiveMode.ADVERSARIAL}:
            topology = "PARALLEL_INDEPENDENT_PATHS_THEN_JUDGE"
        elif plan.mode in {CognitiveMode.DISCOVERY, CognitiveMode.INVESTIGATIVE}:
            topology = "PLANNER_PLUS_PARALLEL_SPECIALISTS"
        else:
            topology = "SEQUENTIAL_LIGHTWEIGHT"

        return CognitiveArchitecture(
            mode=plan.mode,
            topology=topology,
            specialists=tuple(specialists),
            dissolve_after_task=True,
        )

    def _competencies_for(self, name: str) -> tuple[str, ...]:
        mapping = {
            "KAIO": ("meta-reasoning", "goal integrity", "synthesis"),
            "TRUTHGRID": ("fact reconciliation", "contradictions", "canonical state"),
            "JFRIE": ("provenance", "contamination control", "evidence integrity"),
            "RED_TEAM": ("falsification", "counterexamples", "fragility testing"),
            "GOVERNANCE_GATE": ("authority ceiling", "rollback", "blast radius"),
        }
        return mapping.get(name, ("bounded specialist analysis",))
