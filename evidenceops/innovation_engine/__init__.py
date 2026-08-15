"""EvidenceOps Algorithm Foundry.

The package converts verified Master Bible and Secondary Brain lessons into
bounded, deterministic EvidenceOps algorithms.  It performs A0/A1 internal
analysis only and never grants itself external-effect authority.
"""

from .algorithms import (
    ActionSpecificProofValidator,
    AlgorithmOpportunityMiner,
    AlgorithmResult,
    ClaimProofDistanceGuard,
    ControlPlaneIntegrityGuard,
    CorpusSelectionIntegrityEvaluator,
    DirectiveExecutionCompiler,
    FailureToEngineeringGeneCompiler,
    ProofStateTransitionGuard,
    EpistemicDebtPrioritizer,
    OwnerBurdenRouteOptimizer,
    InformationGainRouteSelector,
    KnowledgeUtilityAdoptionGate,
    TerminalFinalityResolver,
    UnknownFrontierPrioritizer,
)
from .evolution import AlgorithmLedger, EvolutionDecision, EvolutionGovernor
from .foundry import EvidenceOpsAlgorithmFoundry, FoundryCycleResult
from .evidenceops_adapter import build_case_payload, extract_master_bible_signals, run_case_cycle
from .replication import CrossImplementationReplicationEvaluator
from .reference_replica import IndependentEvidenceOpsReferenceReplica
from .fevx_bridge import EvidenceOpsInnovationRunner
from .registry import InnovationRegistry

__all__ = [
    "ActionSpecificProofValidator",
    "AlgorithmLedger",
    "AlgorithmOpportunityMiner",
    "AlgorithmResult",
    "ClaimProofDistanceGuard",
    "ControlPlaneIntegrityGuard",
    "CorpusSelectionIntegrityEvaluator",
    "CrossImplementationReplicationEvaluator",
    "DirectiveExecutionCompiler",
    "EvidenceOpsAlgorithmFoundry",
    "EvidenceOpsInnovationRunner",
    "build_case_payload",
    "extract_master_bible_signals",
    "run_case_cycle",
    "EvolutionDecision",
    "EvolutionGovernor",
    "FailureToEngineeringGeneCompiler",
    "FoundryCycleResult",
    "InformationGainRouteSelector",
    "IndependentEvidenceOpsReferenceReplica",
    "KnowledgeUtilityAdoptionGate",
    "OwnerBurdenRouteOptimizer",
    "EpistemicDebtPrioritizer",
    "ProofStateTransitionGuard",
    "InnovationRegistry",
    "TerminalFinalityResolver",
    "UnknownFrontierPrioritizer",
]

__version__ = "1.1.0"