"""Federation Omega Superior Logic runtime."""

__version__ = "3.3.0"

from .digital_twin import CapabilityEdge, FederationDigitalTwin, RouteCandidate
from .evidence_distillation import EvidenceDistiller, EvidenceReceipt
from .mission_ir import HyperSchedule, LaneClass, MissionCompiler, MissionIR, MissionNode, ParallelWave
from .shadow_evolution import PromotionDecision, ShadowEvolutionEngine, TrialScore

__all__ = [
    "CapabilityEdge",
    "EvidenceDistiller",
    "EvidenceReceipt",
    "FederationDigitalTwin",
    "HyperSchedule",
    "LaneClass",
    "MissionCompiler",
    "MissionIR",
    "MissionNode",
    "ParallelWave",
    "PromotionDecision",
    "RouteCandidate",
    "ShadowEvolutionEngine",
    "TrialScore",
]
