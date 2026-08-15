"""Canonical re-export surface for the EvidenceOps deterministic algorithms."""

from .algorithms_common import (
    AUTHORITY_CEILING, AlgorithmOpportunity, AlgorithmResult, canonical_json,
    clamp, number, sequence, sha256, text, unique_text,
)
from .algorithm_algorithm_opportunity_miner import AlgorithmOpportunityMiner
from .algorithm_directive_execution_compiler import DirectiveExecutionCompiler
from .algorithm_claim_proof_distance_guard import ClaimProofDistanceGuard
from .algorithm_unknown_frontier_prioritizer import UnknownFrontierPrioritizer
from .algorithm_information_gain_route_selector import InformationGainRouteSelector
from .algorithm_terminal_finality_resolver import TerminalFinalityResolver
from .algorithm_corpus_selection_integrity_evaluator import CorpusSelectionIntegrityEvaluator
from .algorithm_control_plane_integrity_guard import ControlPlaneIntegrityGuard
from .algorithm_action_specific_proof_validator import ActionSpecificProofValidator
from .algorithm_failure_to_engineering_gene_compiler import FailureToEngineeringGeneCompiler
from .algorithm_proof_state_transition_guard import ProofStateTransitionGuard
from .algorithm_epistemic_debt_prioritizer import EpistemicDebtPrioritizer
from .algorithm_owner_burden_route_optimizer import OwnerBurdenRouteOptimizer
from .algorithm_knowledge_utility_adoption_gate import KnowledgeUtilityAdoptionGate

ALGORITHM_CLASSES = {
    cls.algorithm_id: cls
    for cls in (
        AlgorithmOpportunityMiner,
        DirectiveExecutionCompiler,
        ClaimProofDistanceGuard,
        UnknownFrontierPrioritizer,
        InformationGainRouteSelector,
        TerminalFinalityResolver,
        CorpusSelectionIntegrityEvaluator,
        ControlPlaneIntegrityGuard,
        ActionSpecificProofValidator,
        FailureToEngineeringGeneCompiler,
        ProofStateTransitionGuard,
        EpistemicDebtPrioritizer,
        OwnerBurdenRouteOptimizer,
        KnowledgeUtilityAdoptionGate,
    )
}

__all__ = [
    "AUTHORITY_CEILING", "AlgorithmOpportunity", "AlgorithmResult",
    "canonical_json", "clamp", "number", "sequence", "sha256",
    "text", "unique_text",
    "AlgorithmOpportunityMiner",
    "DirectiveExecutionCompiler",
    "ClaimProofDistanceGuard",
    "UnknownFrontierPrioritizer",
    "InformationGainRouteSelector",
    "TerminalFinalityResolver",
    "CorpusSelectionIntegrityEvaluator",
    "ControlPlaneIntegrityGuard",
    "ActionSpecificProofValidator",
    "FailureToEngineeringGeneCompiler",
    "ProofStateTransitionGuard",
    "EpistemicDebtPrioritizer",
    "OwnerBurdenRouteOptimizer",
    "KnowledgeUtilityAdoptionGate",
    "ALGORITHM_CLASSES",
]