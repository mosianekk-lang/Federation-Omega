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
    def __init__(self) -> None:
        self.core = FluidIntelligenceCore()
        self.compiler = CognitiveCompiler(self.core)
        self.immune = CognitiveImmuneSystem()

    def run(self) -> tuple[LabResult, ...]:
        return (
            self._derivative_corroboration_case(),
            self._high_novelty_compiler_case(),
            self._constraint_inversion_case(),
            self._knockout_resilience_case(),
        )

    def _derivative_corroboration_case(self) -> LabResult:
        items = (
            EvidenceItem("E1", EvidenceState.VERIFIED, "doc-a", "origin-1", 0.9, 0.9),
            EvidenceItem("E2", EvidenceState.SUPPORTED, "summary-a", "origin-1", 0.8, 0.8),
        )
        findings = self.immune.scan_evidence(items)
        passed = any(f.code == "DERIVATIVE_CORROBORATION" for f in findings)
        return LabResult("derivative-corroboration", passed, f"findings={len(findings)}")

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

    def _knockout_resilience_case(self) -> LabResult:
        ctx = ProblemContext(
            objective="test evidentiary resilience",
            stakes=0.8,
            uncertainty=0.4,
            novelty=0.3,
            irreversibility=0.4,
            evidence=(
                EvidenceItem("E1", EvidenceState.VERIFIED, "a", "L1", 0.95, 1.0),
                EvidenceItem("E2", EvidenceState.VERIFIED, "b", "L2", 0.90, 1.0),
            ),
        )
        before = self.core.evidence_resilience(ctx)["resilience"]
        after = self.core.evidence_resilience(self.core.knockout(ctx, "E1"))["resilience"]
        passed = before >= after
        return LabResult("knockout-resilience", passed, f"before={before}; after={after}")
