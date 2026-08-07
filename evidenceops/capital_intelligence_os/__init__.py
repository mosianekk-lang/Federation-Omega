"""EvidenceOps Capital Intelligence OS — durable evidence-native core."""

from .algorithms import AttentionCompressionEngine, CounterfactualCapitalRegret, DecisionReversalThreshold, EpistemicShockIndex, FragilityCascade, TrustDecayClock
from .authority import AuthorityGuard
from .autopilot import Autopilot
from .capital import FinancingStressEngine, GravityEngine
from .decision_algorithms import AssumptionCriticalityRanker, DealSunkCostBiasGuard, EvidenceFreshnessRisk, InformationValuePrioritizer, NoDealDominanceTest, OutcomeCalibrationScore, RegimeSensitivityVector, SynergyDoubleCountDetector, ThesisDecayIndex
from .durable import DurableAutopilotRuntime
from .failure_genome import FailureToRouteGeneCompiler
from .learning import LearningLedger
from .maturity import MaturityEvidence, MaturityGovernor
from .mna import DealLifecycle, MNA_STAGES
from .models import *
from .outcomenet import DataUseConsent, OutcomeNet, OutcomeObservation
from .passport import DealPassport, DealPassportIssuer
from .proofgraph import Contradiction, ProofGraph
from .restricted import RestrictedEntry, RestrictedListRegistry
from .service import CapitalIntelligenceService
from .store import SqliteStateStore
from .tenancy import TenantBoundaryGuard, TenantContext

__version__ = "0.2.0"
__all__ = [
    "AttentionCompressionEngine", "AuthorityGuard", "Autopilot", "CapitalIntelligenceService", "CounterfactualCapitalRegret",
    "DecisionReversalThreshold", "DealLifecycle", "EpistemicShockIndex", "FinancingStressEngine", "FragilityCascade", "GravityEngine",
    "LearningLedger", "MaturityEvidence", "MaturityGovernor", "MNA_STAGES", "Contradiction", "ProofGraph", "TrustDecayClock",
    "AssumptionCriticalityRanker", "DealSunkCostBiasGuard", "EvidenceFreshnessRisk", "InformationValuePrioritizer", "NoDealDominanceTest",
    "OutcomeCalibrationScore", "RegimeSensitivityVector", "SynergyDoubleCountDetector", "ThesisDecayIndex", "DurableAutopilotRuntime",
    "FailureToRouteGeneCompiler", "DataUseConsent", "OutcomeNet", "OutcomeObservation", "DealPassport", "DealPassportIssuer",
    "RestrictedEntry", "RestrictedListRegistry", "SqliteStateStore", "TenantBoundaryGuard", "TenantContext",
]
