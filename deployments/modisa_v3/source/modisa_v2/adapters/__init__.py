"""Compatibility adapters for bounded external worker substrates."""

from .cognitive_binding import (
    CognitiveBindingAdapter,
    CognitiveBindingCollisionError,
    CognitiveBindingError,
    CognitiveBindingReceipt,
    CognitiveBindingState,
    CognitiveBindingVerificationError,
    CognitiveDecisionEnvelope,
)
from .evidenceops_v722 import (
    AdapterCollisionError,
    AdapterError,
    AdapterVerificationError,
    EvidenceOpsV722Adapter,
)

__all__ = [
    "AdapterCollisionError",
    "AdapterError",
    "AdapterVerificationError",
    "CognitiveBindingAdapter",
    "CognitiveBindingCollisionError",
    "CognitiveBindingError",
    "CognitiveBindingReceipt",
    "CognitiveBindingState",
    "CognitiveBindingVerificationError",
    "CognitiveDecisionEnvelope",
    "EvidenceOpsV722Adapter",
]
