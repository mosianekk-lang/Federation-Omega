"""EvidenceOps Capital Intelligence OS — Genesis vertical slice."""

from .algorithms import AttentionCompressionEngine, CounterfactualCapitalRegret, DecisionReversalThreshold, EpistemicShockIndex, FragilityCascade, TrustDecayClock
from .authority import AuthorityGuard
from .autopilot import Autopilot
from .capital import FinancingStressEngine, GravityEngine
from .learning import LearningLedger
from .maturity import MaturityEvidence, MaturityGovernor
from .mna import DealLifecycle, MNA_STAGES
from .models import *
from .proofgraph import Contradiction, ProofGraph
from .service import CapitalIntelligenceService

__version__ = "0.1.0"
__all__ = ["AttentionCompressionEngine", "AuthorityGuard", "Autopilot", "CapitalIntelligenceService", "CounterfactualCapitalRegret", "DecisionReversalThreshold", "DealLifecycle", "EpistemicShockIndex", "FinancingStressEngine", "FragilityCascade", "GravityEngine", "LearningLedger", "MaturityEvidence", "MaturityGovernor", "MNA_STAGES", "Contradiction", "ProofGraph", "TrustDecayClock"]
