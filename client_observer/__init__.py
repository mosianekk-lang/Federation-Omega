"""FUSE-owned client observer contracts.

These modules accept telemetry from authorized local/browser hosts. They do not
claim invisible access to native provider UI surfaces.
"""

from .front_facing_status_observer_v1 import (
    FrontFacingDecision,
    FrontFacingSnapshot,
    FrontFacingStatusObserver,
)

__all__ = [
    "FrontFacingDecision",
    "FrontFacingSnapshot",
    "FrontFacingStatusObserver",
]
