"""Federation Omega continuous learning and algorithm-trigger fabric."""

from .fabric import (
    EventType,
    LearningFabric,
    LearningFabricError,
    PolicyError,
    TriggerActivation,
)
from .integrations import (
    capture_alpha_omega_maintenance,
    capture_resolve_receipt,
)

__all__ = [
    "EventType",
    "LearningFabric",
    "LearningFabricError",
    "PolicyError",
    "TriggerActivation",
    "capture_alpha_omega_maintenance",
    "capture_resolve_receipt",
]

__version__ = "1.0.0"
