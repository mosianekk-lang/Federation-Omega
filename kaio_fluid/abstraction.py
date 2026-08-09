from __future__ import annotations

from dataclasses import dataclass

from .models import ProblemContext


@dataclass(frozen=True)
class ProblemAbstraction:
    objective: str
    actors: tuple[str, ...]
    constraints: tuple[str, ...]
    assumptions: tuple[str, ...]
    dependencies: tuple[str, ...]
    unknowns: tuple[str, ...]


class ProblemAbstractionEngine:
    """Create a minimal explicit structural representation from a problem context."""

    def abstract(
        self,
        ctx: ProblemContext,
        *,
        actors: tuple[str, ...] = (),
        dependencies: tuple[str, ...] = (),
        unknowns: tuple[str, ...] = (),
    ) -> ProblemAbstraction:
        return ProblemAbstraction(
            objective=ctx.objective.strip(),
            actors=tuple(dict.fromkeys(a.strip() for a in actors if a.strip())),
            constraints=tuple(dict.fromkeys(c.strip() for c in ctx.constraints if c.strip())),
            assumptions=tuple(dict.fromkeys(a.strip() for a in ctx.assumptions if a.strip())),
            dependencies=tuple(dict.fromkeys(d.strip() for d in dependencies if d.strip())),
            unknowns=tuple(dict.fromkeys(u.strip() for u in unknowns if u.strip())),
        )

    def complexity(self, model: ProblemAbstraction) -> int:
        return (
            len(model.actors)
            + len(model.constraints)
            + len(model.assumptions)
            + len(model.dependencies)
            + len(model.unknowns)
        )
