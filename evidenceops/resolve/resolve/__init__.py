"""EvidenceOps RESOLVE."""

from .engine import ResolveEngine
from .models import CompletionGate, EvidenceJob, ExecutionLane, LaneResult, ResolvePolicy

__all__ = [
    "CompletionGate",
    "EvidenceJob",
    "ExecutionLane",
    "LaneResult",
    "ResolveEngine",
    "ResolvePolicy",
]

__version__ = "1.0.0"
