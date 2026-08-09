from __future__ import annotations

from .core import FluidIntelligenceCore
from .models import CognitiveMode, ProblemContext, ReasoningPlan


class CognitiveCompiler:
    """Compile a problem into a bounded temporary cognitive architecture."""

    def __init__(self, core: FluidIntelligenceCore | None = None) -> None:
        self.core = core or FluidIntelligenceCore()

    def compile(self, ctx: ProblemContext) -> ReasoningPlan:
        ctx = ctx.bounded()
        budget = self.core.reasoning_budget(ctx)
        novelty = self.core.novelty_score(ctx)

        if budget < 0.25 and novelty < 0.25:
            mode = CognitiveMode.REFLEX
            depth = 1
        elif budget < 0.45:
            mode = CognitiveMode.ANALYTICAL
            depth = 2
        elif novelty >= 0.70 and budget >= 0.65:
            mode = CognitiveMode.DEEP_SYNTHESIS
            depth = 5
        elif novelty >= 0.60:
            mode = CognitiveMode.DISCOVERY
            depth = 4
        elif ctx.uncertainty >= 0.60:
            mode = CognitiveMode.INVESTIGATIVE
            depth = 4
        elif ctx.stakes >= 0.70:
            mode = CognitiveMode.ADVERSARIAL
            depth = 4
        else:
            mode = CognitiveMode.ANALYTICAL
            depth = 3

        specialists = ["KAIO"]
        primitives = ["PROOF_CLASSIFICATION", "PROVENANCE", "STOPPING_RULE"]

        if mode in {CognitiveMode.INVESTIGATIVE, CognitiveMode.DISCOVERY, CognitiveMode.DEEP_SYNTHESIS}:
            specialists.extend(["TRUTHGRID", "JFRIE"])
            primitives.extend(["HYPOTHESIS_COMPETITION", "INFORMATION_GAIN", "REFRAMING"])

        if ctx.stakes >= 0.65:
            specialists.append("RED_TEAM")
            primitives.append("FALSIFICATION")

        if ctx.irreversibility >= 0.60:
            specialists.append("GOVERNANCE_GATE")
            primitives.extend(["ROLLBACK_CHECK", "BLAST_RADIUS"])

        if ctx.novelty >= 0.55:
            primitives.extend(["ABSTRACTION", "CONSTRAINT_INVERSION", "REPRESENTATION_SWITCH"])

        notes = (
            f"reasoning_budget={budget:.3f}",
            f"novelty_score={novelty:.3f}",
            "truth-promotion remains outside the fluid core",
        )

        return ReasoningPlan(
            mode=mode,
            specialists=tuple(dict.fromkeys(specialists)),
            primitives=tuple(dict.fromkeys(primitives)),
            verification_depth=depth,
            simulation_depth=max(1, depth - 1),
            stop_threshold=max(0.02, 0.12 - budget * 0.08),
            authority_ceiling="A1_INTERNAL",
            external_effect=False,
            notes=notes,
        )
