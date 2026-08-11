from __future__ import annotations

from dataclasses import replace

from .models import Hypothesis, ProblemContext, independent_source_count


class FluidIntelligenceCore:
    """Pure, deterministic cognitive primitives.

    This layer generates candidate reasoning structures. It never promotes facts,
    mutates evidence, or performs external actions.
    """

    def novelty_score(self, ctx: ProblemContext) -> float:
        ctx = ctx.bounded()
        evidence_penalty = 0.15 if not ctx.evidence else 0.0
        assumption_penalty = min(0.2, len(ctx.assumptions) * 0.03)
        return min(1.0, ctx.novelty + evidence_penalty + assumption_penalty)

    def reasoning_budget(self, ctx: ProblemContext) -> float:
        ctx = ctx.bounded()
        return (
            ctx.stakes * 0.30
            + ctx.uncertainty * 0.25
            + ctx.novelty * 0.25
            + ctx.irreversibility * 0.20
        )

    def reframe(self, ctx: ProblemContext) -> tuple[str, ...]:
        objective = ctx.objective.strip()
        return (
            f"DIRECT: {objective}",
            f"PROOF: What propositions must be established to achieve: {objective}?",
            f"CONSTRAINT: Which constraints actually prevent: {objective}?",
            f"DUAL: What observations would exist if the desired conclusion were false?",
            f"SUBSTITUTION: Can the outcome be reached without the apparently required missing input?",
            f"FUTURE-BACK: Starting from success, what prerequisite states must already be true?",
        )

    def generate_hypotheses(self, ctx: ProblemContext) -> tuple[Hypothesis, ...]:
        base = ctx.objective.strip()
        return (
            Hypothesis(
                id="H1",
                statement=f"Primary model: the direct framing of '{base}' is substantially correct.",
                confidence=max(0.05, 1.0 - ctx.uncertainty),
                expected_observations=("direct supporting evidence", "consistent chronology"),
                falsifiers=("authenticated contradiction", "missing required causal bridge"),
            ),
            Hypothesis(
                id="H2",
                statement=f"Alternative model: '{base}' is blocked by a hidden constraint or wrong representation.",
                confidence=min(0.8, 0.25 + ctx.novelty * 0.5),
                expected_observations=("repeated exceptions", "stalled direct route"),
                falsifiers=("simple direct route succeeds with verified readback",),
            ),
            Hypothesis(
                id="H3",
                statement=f"Null/third-model: available evidence is insufficient to prefer a single explanation for '{base}'.",
                confidence=min(0.9, 0.2 + ctx.uncertainty * 0.65),
                expected_observations=("low evidence independence", "material unresolved gaps"),
                falsifiers=("multiple independent verified proof routes converge",),
            ),
        )

    def information_gain_priority(self, ctx: ProblemContext) -> tuple[str, ...]:
        priorities: list[tuple[float, str]] = []
        for item in ctx.evidence:
            score = (1.0 - item.reliability) * item.materiality
            priorities.append((score, f"REVALIDATE:{item.id}"))
        for assumption in ctx.assumptions:
            priorities.append((0.85, f"VERIFY_ASSUMPTION:{assumption}"))
        for constraint in ctx.constraints:
            priorities.append((0.75, f"TEST_CONSTRAINT:{constraint}"))
        priorities.sort(key=lambda x: (-x[0], x[1]))
        return tuple(label for _, label in priorities)

    def evidence_resilience(self, ctx: ProblemContext) -> dict[str, float | int]:
        if not ctx.evidence:
            return {"items": 0, "independent_lineages": 0, "mean_reliability": 0.0, "resilience": 0.0}
        independent = independent_source_count(ctx.evidence)
        mean_rel = sum(e.reliability for e in ctx.evidence) / len(ctx.evidence)
        diversity = min(1.0, independent / max(1, len(ctx.evidence)))
        resilience = round(mean_rel * 0.65 + diversity * 0.35, 4)
        return {
            "items": len(ctx.evidence),
            "independent_lineages": independent,
            "mean_reliability": round(mean_rel, 4),
            "resilience": resilience,
        }

    def knockout(self, ctx: ProblemContext, evidence_id: str) -> ProblemContext:
        return replace(ctx, evidence=tuple(e for e in ctx.evidence if e.id != evidence_id))
