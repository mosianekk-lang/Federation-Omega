from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Principle:
    id: str
    kind: str
    statement: str
    operational_use: str
    limit: str


PRINCIPLES = (
    Principle("CAUSALITY", "scientific", "Prefer causal mechanisms over correlation.", "Require interventions or competing explanations.", "Causality may remain unidentified from observational data."),
    Principle("CONSERVATION", "physical", "Account for conserved quantities and resource budgets.", "Reject plans whose time, cost, energy or information appears from nowhere.", "The relevant boundary must be defined."),
    Principle("ENTROPY", "physical_metaphor", "Unmaintained systems accumulate disorder.", "Budget observability, backups, pruning and repair.", "Not a literal thermodynamic calculation for software."),
    Principle("BAYES", "mathematical", "Update beliefs in proportion to prior odds and likelihood.", "Attach confidence and revise it when evidence arrives.", "Bad priors and dependent evidence distort results."),
    Principle("INFORMATION", "mathematical", "Prefer actions with high expected information gain.", "Choose the smallest safe experiment that separates hypotheses.", "Information value is task-dependent."),
    Principle("CONTROL", "engineering", "Stable control needs observation, comparison and correction.", "Use feedback, bounded gain, circuit breakers and rollback.", "Delayed feedback can destabilize a loop."),
    Principle("GOODHART", "systems_heuristic", "A target metric can cease to be a useful measure.", "Use multiple fruit measures and audit gaming.", "A heuristic, not a universal theorem."),
    Principle("OCCAM", "epistemic_heuristic", "Prefer the least-assumptive explanation that fits evidence.", "Prune needless agents, artifacts and dependencies.", "Simplicity does not prove truth."),
    Principle("FALSIFICATION", "scientific_method", "A useful claim exposes how it could be disproved.", "Define negative controls and failure thresholds before execution.", "Some historical or probabilistic claims are not cleanly falsifiable."),
    Principle("KUNG_FU_ECONOMY", "strategic_heuristic", "Use minimum sufficient motion for maximum verified effect.", "Prefer precise reversible actions over forceful broad changes.", "A philosophy, not physical law."),
    Principle("KUNG_FU_YIELD", "strategic_heuristic", "Redirect constraints rather than contest them blindly.", "Switch authorized routes and isolate blockers.", "Never use this to bypass authority."),
    Principle("BEGINNERS_MIND", "strategic_heuristic", "Keep observations separable from assumptions.", "Re-read live contracts and invite contradiction.", "Openness does not replace expertise."),
)


def catalogue() -> list[dict[str, str]]:
    return [asdict(p) for p in PRINCIPLES]
