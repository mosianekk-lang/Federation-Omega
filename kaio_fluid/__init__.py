"""KAIO Ω Fluid Intelligence Core.

Proof-bound adaptive cognition for Federation Omega.
"""

from .models import (
    CognitiveMode,
    EvidenceState,
    Hypothesis,
    ProblemContext,
    ReasoningPlan,
)
from .core import FluidIntelligenceCore
from .compiler import CognitiveCompiler
from .immune import CognitiveImmuneSystem

__all__ = [
    "CognitiveMode",
    "EvidenceState",
    "Hypothesis",
    "ProblemContext",
    "ReasoningPlan",
    "FluidIntelligenceCore",
    "CognitiveCompiler",
    "CognitiveImmuneSystem",
]
