from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import prod


class TruthState(str, Enum):
    PROVED = "PROVED"
    PROVED_WITH_LIMITATION = "PROVED_WITH_LIMITATION"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    NOT_LOCATED = "NOT_LOCATED"
    PRODUCTION_REQUIRED = "PRODUCTION_REQUIRED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class DecisionReadiness(str, Enum):
    READY = "READY"
    CONDITIONAL = "CONDITIONAL"
    NOT_READY = "NOT_READY"


@dataclass(frozen=True)
class ClosureCandidate:
    action_id: str
    materiality: float
    downstream_impact: float
    recovery_probability: float
    deadline_weight: float
    contradiction_value: float
    effort: float
    executable: bool = True
    external_blocker: bool = False

    def score(self) -> float:
        if not self.executable or self.external_blocker:
            return 0.0
        return prod((self.materiality, self.downstream_impact, self.recovery_probability, self.deadline_weight, self.contradiction_value)) / max(self.effort, 0.01)


@dataclass(frozen=True)
class CompletionVector:
    accessible_corpus_exhausted: bool
    material_sources_processed: bool
    executable_internal_gap_count: int
    external_production_gap_count: int
    material_contradiction_count: int
    adversarial_review_passed: bool
    live_writer_enforcement_passed: bool
    regression_passed: bool
    dashboard_live_generated: bool

    def internal_complete(self) -> bool:
        return all((
            self.accessible_corpus_exhausted,
            self.material_sources_processed,
            self.executable_internal_gap_count == 0,
            self.material_contradiction_count == 0,
            self.adversarial_review_passed,
            self.live_writer_enforcement_passed,
            self.regression_passed,
            self.dashboard_live_generated,
        ))

    def evidence_availability(self) -> str:
        if not self.internal_complete():
            return "PARTIAL"
        return "PRODUCTION_REQUIRED" if self.external_production_gap_count else "PASS"

    def decision_readiness(self) -> DecisionReadiness:
        if not self.internal_complete():
            return DecisionReadiness.NOT_READY
        return DecisionReadiness.CONDITIONAL if self.external_production_gap_count else DecisionReadiness.READY


class TruthGridVNext:
    @staticmethod
    def rank_closure(candidates: tuple[ClosureCandidate, ...]) -> tuple[ClosureCandidate, ...]:
        return tuple(sorted(candidates, key=lambda c: (-c.score(), c.action_id)))
