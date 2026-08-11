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
from .federation_validation import (
    AutoFixLaboratory,
    CapabilityForge,
    CapabilityForgeResult,
    CapabilityProbe,
    ContinuityForge,
    ContinuityProbe,
    FederationEvaluationContract,
    MaturityState,
    RecoveryTrace,
    promote_contract,
)
from .federation_validation_evolution import to_evolution_governor_metrics
from .scientia import (
    EpistemicState,
    Hypothesis,
    ScientiaKernel,
    ScientificObservation,
)

__all__ = [
    "BENCHMARK_WEIGHTS",
    "FATAL_FAILURES",
    "AutoFixLaboratory",
    "BenchmarkEvaluation",
    "CandidatePromotionDecision",
    "Capability",
    "CapabilityForge",
    "CapabilityForgeResult",
    "CapabilityPlan",
    "CapabilityProbe",
    "ContinuityForge",
    "ContinuityProbe",
    "EpistemicState",
    "FederationEvaluationContract",
    "Hypothesis",
    "MaturityState",
    "RecoveryTrace",
    "ScientiaKernel",
    "ScientificObservation",
    "SurfaceState",
    "build_innovation_frontier",
    "evaluate_benchmark",
    "evaluate_candidate_promotion",
    "promote_contract",
    "select_minimum_sufficient_capabilities",
    "select_next_case",
    "to_evolution_governor_metrics",
    "to_evolution_metrics",
]
