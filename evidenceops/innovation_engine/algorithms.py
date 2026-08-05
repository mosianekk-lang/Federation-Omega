"""Canonical re-export surface for the EvidenceOps deterministic algorithms."""

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, canonical_json,
    clamp, number, sequence, sha256, text, unique_text,
)
from .algorithms_mining import (
    AlgorithmOpportunityMiner, DirectiveExecutionCompiler,
    ClaimProofDistanceGuard, UnknownFrontierPrioritizer,
    InformationGainRouteSelector,
)
from .algorithms_integrity import (
    TerminalFinalityResolver, CorpusSelectionIntegrityEvaluator,
    ControlPlaneIntegrityGuard, ActionSpecificProofValidator,
    FailureToEngineeringGeneCompiler,
)
from .algorithms_governance import (
    ProofStateTransitionGuard, EpistemicDebtPrioritizer,
    OwnerBurdenRouteOptimizer,
)

ALGORITHM_CLASSES = {
    cls.algorithm_id: cls
    for cls in (
        AlgorithmOpportunityMiner, DirectiveExecutionCompiler,
        ClaimProofDistanceGuard, UnknownFrontierPrioritizer,
        InformationGainRouteSelector, TerminalFinalityResolver,
        CorpusSelectionIntegrityEvaluator, ControlPlaneIntegrityGuard,
        ActionSpecificProofValidator, FailureToEngineeringGeneCompiler,
        ProofStateTransitionGuard, EpistemicDebtPrioritizer,
        OwnerBurdenRouteOptimizer,
    )
}

__all__ = [
    "AUTHORITY_CEILING", "AlgorithmOpportunity", "AlgorithmResult",
    "canonical_json", "clamp", "number", "sequence", "sha256",
    "text", "unique_text", "AlgorithmOpportunityMiner",
    "DirectiveExecutionCompiler", "ClaimProofDistanceGuard",
    "UnknownFrontierPrioritizer", "InformationGainRouteSelector",
    "TerminalFinalityResolver", "CorpusSelectionIntegrityEvaluator",
    "ControlPlaneIntegrityGuard", "ActionSpecificProofValidator",
    "FailureToEngineeringGeneCompiler", "ProofStateTransitionGuard",
    "EpistemicDebtPrioritizer", "OwnerBurdenRouteOptimizer",
    "ALGORITHM_CLASSES",
]
