from __future__ import annotations

from dataclasses import dataclass

from .compiler import CognitiveCompiler
from .core import FluidIntelligenceCore
from .immune import CognitiveImmuneSystem
from .models import EvidenceItem, EvidenceState, ProblemContext


@dataclass(frozen=True)
class LabResult:
    name: str
    passed: bool
    details: str


class SyntheticProblemLaboratory:
    """Deterministic adversarial laboratory for KAIO fluid-intelligence invariants.

    The cases are deliberately synthetic. They prove local algorithm behaviour,
    not real-world correctness or provider-hosted operation.
    """

    def __init__(self) -> None:
        self.core = FluidIntelligenceCore()
        self.compiler = CognitiveCompiler(self.core)
        self.immune = CognitiveImmuneSystem()

    def run(self) -> tuple[LabResult, ...]:
        cases = (
            self._derivative_corroboration_case,
            self._certainty_inflation_case,
            self._missing_source_identity_case,
            self._clean_independent_evidence_case,
            self._high_novelty_compiler_case,
            self._low_risk_reflex_case,
            self._uncertain_investigative_case,
            self._high_stakes_adversarial_case,
            self._irreversible_governance_case,
            self._novel_representation_switch_case,
            self._constraint_inversion_case,
            self._assumption_precedes_constraint_case,
            self._weak_evidence_revalidation_case,
            self._hypothesis_competition_case,
            self._null_hypothesis_uncertainty_case,
            self._reframing_diversity_case,
            self._no_evidence_novelty_penalty_case,
            self._assumption_novelty_penalty_case,
            self._reasoning_budget_monotonicity_case,
            self._independent_lineage_resilience_case,
            self._derivative_lineage_resilience_case,
            self._knockout_resilience_case,
            self._missing_knockout_noop_case,
            self._bounded_context_case,
            self._authority_ceiling_case,
        )
        results = tuple(case() for case in cases)
        if len(results) != 25:
            raise AssertionError(f"expected 25 laboratory cases, got {len(results)}")
        return results

    @staticmethod
    def _item(
        item_id: str,
        state: EvidenceState,
        source: str,
        lineage: str,
        reliability: float,
        materiality: float = 1.0,
    ) -> EvidenceItem:
        return EvidenceItem(item_id, state, source, lineage, reliability, materiality)

    def _derivative_corroboration_case(self) -> LabResult:
        items = (
            self._item("E1", EvidenceState.VERIFIED, "doc-a", "origin-1", 0.9),
            self._item("E2", EvidenceState.SUPPORTED, "summary-a", "origin-1", 0.8),
        )
        findings = self.immune.scan_evidence(items)
        passed = any(f.code == "DERIVATIVE_CORROBORATION" for f in findings)
        return LabResult("derivative-corroboration", passed, f"findings={len(findings)}")

    def _certainty_inflation_case(self) -> LabResult:
        items = (self._item("E1", EvidenceState.UNVERIFIED, "claim", "L1", 0.99),)
        findings = self.immune.scan_evidence(items)
        passed = any(f.code == "CERTAINTY_INFLATION" for f in findings)
        return LabResult("certainty-inflation", passed, repr(tuple(f.code for f in findings)))

    def _missing_source_identity_case(self) -> LabResult:
        items = (self._item("E1", EvidenceState.SUPPORTED, "", "L1", 0.7),)
        findings = self.immune.scan_evidence(items)
        passed = (
            any(f.code == "MISSING_SOURCE_IDENTITY" for f in findings)
            and not self.immune.promotion_allowed(items)
        )
        return LabResult("missing-source-identity", passed, repr(tuple(f.code for f in findings)))

    def _clean_independent_evidence_case(self) -> LabResult:
        items = (
            self._item("E1", EvidenceState.VERIFIED, "a", "L1", 0.9),
            self._item("E2", EvidenceState.VERIFIED, "b", "L2", 0.9),
        )
        findings = self.immune.scan_evidence(items)
        passed = not findings and self.immune.promotion_allowed(items)
        return LabResult("clean-independent-evidence", passed, f"findings={len(findings)}")

    def _high_novelty_compiler_case(self) -> LabResult:
        ctx = ProblemContext(
            objective="solve an unfamiliar high-stakes blocked problem",
            stakes=0.9,
            uncertainty=0.9,
            novelty=0.95,
            irreversibility=0.8,
        )
        plan = self.compiler.compile(ctx)
        passed = plan.mode.value == "DEEP_SYNTHESIS" and not plan.external_effect
        return LabResult("high-novelty-compiler", passed, f"mode={plan.mode.value}")

    def _low_risk_reflex_case(self) -> LabResult:
        ctx = ProblemContext("routine reversible lookup", 0.05, 0.05, 0.05, 0.05)
        plan = self.compiler.compile(ctx)
        passed = plan.mode.value == "REFLEX" and plan.verification_depth == 1
        return LabResult("low-risk-reflex", passed, f"mode={plan.mode.value}")

    def _uncertain_investigative_case(self) -> LabResult:
        ctx = ProblemContext("resolve uncertain familiar matter", 0.5, 0.8, 0.3, 0.3)
        plan = self.compiler.compile(ctx)
        passed = plan.mode.value == "INVESTIGATIVE" and "TRUTHGRID" in plan.specialists
        return LabResult("uncertain-investigative", passed, f"mode={plan.mode.value}")

    def _high_stakes_adversarial_case(self) -> LabResult:
        ctx = ProblemContext("challenge a consequential conclusion", 0.9, 0.3, 0.3, 0.3)
        plan = self.compiler.compile(ctx)
        passed = plan.mode.value == "ADVERSARIAL" and "RED_TEAM" in plan.specialists
        return LabResult("high-stakes-adversarial", passed, f"mode={plan.mode.value}")

    def _irreversible_governance_case(self) -> LabResult:
        ctx = ProblemContext("plan irreversible action", 0.6, 0.3, 0.3, 0.9)
        plan = self.compiler.compile(ctx)
        passed = "GOVERNANCE_GATE" in plan.specialists and "ROLLBACK_CHECK" in plan.primitives
        return LabResult("irreversible-governance", passed, repr(plan.specialists))

    def _novel_representation_switch_case(self) -> LabResult:
        ctx = ProblemContext("solve unusual representation", 0.5, 0.4, 0.7, 0.2)
        plan = self.compiler.compile(ctx)
        passed = "REPRESENTATION_SWITCH" in plan.primitives and "ABSTRACTION" in plan.primitives
        return LabResult("novel-representation-switch", passed, repr(plan.primitives))

    def _constraint_inversion_case(self) -> LabResult:
        ctx = ProblemContext(
            objective="establish proposition P",
            stakes=0.7,
            uncertainty=0.7,
            novelty=0.6,
            irreversibility=0.4,
            constraints=("document X unavailable",),
            assumptions=("document X is required",),
        )
        priorities = self.core.information_gain_priority(ctx)
        passed = any(p.startswith("VERIFY_ASSUMPTION") for p in priorities)
        return LabResult("constraint-inversion", passed, repr(priorities))

    def _assumption_precedes_constraint_case(self) -> LabResult:
        ctx = ProblemContext(
            "test ordering", 0.4, 0.4, 0.4, 0.2,
            assumptions=("A",), constraints=("C",),
        )
        priorities = self.core.information_gain_priority(ctx)
        passed = priorities[:2] == ("VERIFY_ASSUMPTION:A", "TEST_CONSTRAINT:C")
        return LabResult("assumption-priority", passed, repr(priorities))

    def _weak_evidence_revalidation_case(self) -> LabResult:
        ctx = ProblemContext(
            "revalidate weak material evidence", 0.5, 0.5, 0.4, 0.2,
            evidence=(self._item("WEAK", EvidenceState.SUPPORTED, "x", "L1", 0.1, 1.0),),
        )
        priorities = self.core.information_gain_priority(ctx)
        passed = priorities and priorities[0] == "REVALIDATE:WEAK"
        return LabResult("weak-evidence-revalidation", passed, repr(priorities))

    def _hypothesis_competition_case(self) -> LabResult:
        ctx = ProblemContext("explain an ambiguous event", 0.6, 0.7, 0.6, 0.3)
        hypotheses = self.core.generate_hypotheses(ctx)
        passed = len(hypotheses) == 3 and {h.id for h in hypotheses} == {"H1", "H2", "H3"}
        return LabResult("hypothesis-competition", passed, repr(tuple(h.id for h in hypotheses)))

    def _null_hypothesis_uncertainty_case(self) -> LabResult:
        low = self.core.generate_hypotheses(ProblemContext("x", 0.5, 0.1, 0.4, 0.2))[2]
        high = self.core.generate_hypotheses(ProblemContext("x", 0.5, 0.9, 0.4, 0.2))[2]
        passed = high.confidence > low.confidence
        return LabResult("null-hypothesis-uncertainty", passed, f"low={low.confidence}; high={high.confidence}")

    def _reframing_diversity_case(self) -> LabResult:
        frames = self.core.reframe(ProblemContext("reach outcome", 0.5, 0.5, 0.5, 0.2))
        prefixes = {frame.split(":", 1)[0] for frame in frames}
        passed = len(frames) == 6 and len(prefixes) == 6
        return LabResult("reframing-diversity", passed, repr(tuple(sorted(prefixes))))

    def _no_evidence_novelty_penalty_case(self) -> LabResult:
        without = self.core.novelty_score(ProblemContext("x", 0.3, 0.3, 0.3, 0.2))
        with_ev = self.core.novelty_score(
            ProblemContext(
                "x", 0.3, 0.3, 0.3, 0.2,
                evidence=(self._item("E", EvidenceState.VERIFIED, "s", "L", 0.9),),
            )
        )
        passed = without > with_ev
        return LabResult("no-evidence-novelty-penalty", passed, f"without={without}; with={with_ev}")

    def _assumption_novelty_penalty_case(self) -> LabResult:
        base = self.core.novelty_score(
            ProblemContext(
                "x", 0.3, 0.3, 0.3, 0.2,
                evidence=(self._item("E", EvidenceState.VERIFIED, "s", "L", 0.9),),
            )
        )
        assumed = self.core.novelty_score(
            ProblemContext(
                "x", 0.3, 0.3, 0.3, 0.2,
                evidence=(self._item("E", EvidenceState.VERIFIED, "s", "L", 0.9),),
                assumptions=("a", "b"),
            )
        )
        passed = assumed > base
        return LabResult("assumption-novelty-penalty", passed, f"base={base}; assumed={assumed}")

    def _reasoning_budget_monotonicity_case(self) -> LabResult:
        low = self.core.reasoning_budget(ProblemContext("x", 0.1, 0.1, 0.1, 0.1))
        high = self.core.reasoning_budget(ProblemContext("x", 0.9, 0.9, 0.9, 0.9))
        passed = high > low
        return LabResult("reasoning-budget-monotonicity", passed, f"low={low}; high={high}")

    def _independent_lineage_resilience_case(self) -> LabResult:
        ctx = ProblemContext(
            "resilience", 0.5, 0.4, 0.3, 0.2,
            evidence=(
                self._item("E1", EvidenceState.VERIFIED, "a", "L1", 0.8),
                self._item("E2", EvidenceState.VERIFIED, "b", "L2", 0.8),
            ),
        )
        result = self.core.evidence_resilience(ctx)
        passed = result["independent_lineages"] == 2 and result["resilience"] > 0.8
        return LabResult("independent-lineage-resilience", passed, repr(result))

    def _derivative_lineage_resilience_case(self) -> LabResult:
        independent = ProblemContext(
            "resilience", 0.5, 0.4, 0.3, 0.2,
            evidence=(
                self._item("E1", EvidenceState.VERIFIED, "a", "L1", 0.8),
                self._item("E2", EvidenceState.VERIFIED, "b", "L2", 0.8),
            ),
        )
        derivative = ProblemContext(
            "resilience", 0.5, 0.4, 0.3, 0.2,
            evidence=(
                self._item("E1", EvidenceState.VERIFIED, "a", "L1", 0.8),
                self._item("E2", EvidenceState.VERIFIED, "b", "L1", 0.8),
            ),
        )
        a = self.core.evidence_resilience(independent)["resilience"]
        b = self.core.evidence_resilience(derivative)["resilience"]
        passed = a > b
        return LabResult("derivative-lineage-resilience", passed, f"independent={a}; derivative={b}")

    def _knockout_resilience_case(self) -> LabResult:
        ctx = ProblemContext(
            objective="test evidentiary resilience",
            stakes=0.8,
            uncertainty=0.4,
            novelty=0.3,
            irreversibility=0.4,
            evidence=(
                self._item("E1", EvidenceState.VERIFIED, "a", "L1", 0.95),
                self._item("E2", EvidenceState.VERIFIED, "b", "L2", 0.90),
            ),
        )
        before = self.core.evidence_resilience(ctx)["resilience"]
        knocked = self.core.knockout(ctx, "E1")
        passed = len(knocked.evidence) == 1 and knocked.evidence[0].id == "E2"
        return LabResult("knockout-resilience", passed, f"before={before}; remaining={len(knocked.evidence)}")

    def _missing_knockout_noop_case(self) -> LabResult:
        ctx = ProblemContext(
            "noop", 0.4, 0.4, 0.4, 0.2,
            evidence=(self._item("E1", EvidenceState.VERIFIED, "a", "L1", 0.9),),
        )
        after = self.core.knockout(ctx, "MISSING")
        passed = after.evidence == ctx.evidence
        return LabResult("missing-knockout-noop", passed, repr(tuple(e.id for e in after.evidence)))

    def _bounded_context_case(self) -> LabResult:
        ctx = ProblemContext("bounds", 2.0, -1.0, 3.0, -2.0).bounded()
        passed = (ctx.stakes, ctx.uncertainty, ctx.novelty, ctx.irreversibility) == (1.0, 0.0, 1.0, 0.0)
        return LabResult("bounded-context", passed, repr((ctx.stakes, ctx.uncertainty, ctx.novelty, ctx.irreversibility)))

    def _authority_ceiling_case(self) -> LabResult:
        plan = self.compiler.compile(ProblemContext("authority", 1.0, 1.0, 1.0, 1.0))
        passed = plan.authority_ceiling == "A1_INTERNAL" and plan.external_effect is False
        return LabResult("authority-ceiling", passed, f"authority={plan.authority_ceiling}; effect={plan.external_effect}")
