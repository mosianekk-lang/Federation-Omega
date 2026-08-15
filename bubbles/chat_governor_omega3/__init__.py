"""Bubbles Adaptive Chat Governor Ω3.1.

Truth boundary: this package governs Bubbles workflows routed through it. It does
not modify hidden ChatGPT context management, provider serving infrastructure,
or connector calls that bypass this middleware.
"""

from .routing import MissionCompiler, MissionPlan, MemoryGovernor
from .runtime import ConnectorGateway
from .state import DurableState, EvidencePointer
from .dag import DAGExecutor, Lane, LaneState
from .completion import ChatGovCompletionInterlock, CompletionReconcileResult

__all__ = [
    "MissionCompiler", "MissionPlan", "MemoryGovernor", "ConnectorGateway",
    "DurableState", "EvidencePointer", "DAGExecutor", "Lane", "LaneState",
    "ChatGovCompletionInterlock", "CompletionReconcileResult",
]

__version__ = "3.1.0"
