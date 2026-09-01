"""Federation Omega Superior Logic runtime."""

__version__ = "3.3.0"

from .digital_twin import CapabilityEdge, FederationDigitalTwin, RouteCandidate
from .evidence_distillation import EvidenceDistiller, EvidenceReceipt
from .hyperperformance import CounterfactualRoute, HyperperformanceController, MissionPlan
from .mission_ir import HyperSchedule, LaneClass, MissionCompiler, MissionIR, MissionNode, ParallelWave
from .opportunity_discovery import Opportunity, OpportunityDiscoveryEngine
from .shadow_evolution import PromotionDecision, ShadowEvolutionEngine, TrialScore

__all__ = [
    "CapabilityEdge",
    "CounterfactualRoute",
    "EvidenceDistiller",
    "EvidenceReceipt",
    "FederationDigitalTwin",
    "HyperSchedule",
    "HyperperformanceController",
    "LaneClass",
    "MissionCompiler",
    "MissionIR",
    "MissionNode",
    "MissionPlan",
    "Opportunity",
    "OpportunityDiscoveryEngine",
    "ParallelWave",
    "PromotionDecision",
    "RouteCandidate",
    "ShadowEvolutionEngine",
    "TrialScore",
]
