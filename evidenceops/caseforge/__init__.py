"""CASEFORGE-Ω scientific benchmark and evolution layer for EvidenceOps."""

from .core import (
    BENCHMARK_WEIGHTS,
    FATAL_FAILURES,
    BenchmarkEvaluation,
    CandidatePromotionDecision,
    evaluate_benchmark,
    evaluate_candidate_promotion,
    select_next_case,
    to_evolution_metrics,
)
from .federation_adapter import (
    Capability,
    CapabilityPlan,
    SurfaceState,
    build_innovation_frontier,
    select_minimum_sufficient_capabilities,
)
from .scientia import (
    EpistemicState,
    Hypothesis,
    ScientiaKernel,
    ScientificObservation,
)

__all__ = [
    "BENCHMARK_WEIGHTS",
    "FATAL_FAILURES",
    "BenchmarkEvaluation",
    "CandidatePromotionDecision",
    "Capability",
    "CapabilityPlan",
    "EpistemicState",
    "Hypothesis",
    "ScientiaKernel",
    "ScientificObservation",
    "SurfaceState",
    "build_innovation_frontier",
    "evaluate_benchmark",
    "evaluate_candidate_promotion",
    "select_minimum_sufficient_capabilities",
    "select_next_case",
    "to_evolution_metrics",
]
