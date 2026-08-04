"""Federation Omega continuous learning and algorithm-trigger fabric."""

from .fabric import (
    EventType,
    LearningFabric,
    LearningFabricError,
    PolicyError,
    TriggerActivation,
)

__all__ = [
    "EventType",
    "LearningFabric",
    "LearningFabricError",
    "PolicyError",
    "TriggerActivation",
]

__version__ = "1.0.0"
