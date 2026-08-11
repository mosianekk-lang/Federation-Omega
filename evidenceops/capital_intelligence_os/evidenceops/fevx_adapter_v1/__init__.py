"""EvidenceOps ↔ FEVX CSE supervised read-only adapter."""

from .adapter import EvidenceOpsFEVXAdapter
from .contracts import BoundaryViolation, PacketValidationError, validate_packet
from .store import DerivedStore

__version__ = "1.1.0"
__all__ = [
    "EvidenceOpsFEVXAdapter",
    "DerivedStore",
    "BoundaryViolation",
    "PacketValidationError",
    "validate_packet",
]
