"""Federation Omega cybernetic working-memory controller v11.

This package is a deterministic A1-internal control kernel. It does not create
background access, provider authority, human review, certification, or external
effects.
"""

from .audio_v4_binding import AudioV4Snapshot, assess_audio_v4_snapshot
from .canary import run_privacy_safe_canary
from .controller import CyberneticController, default_reflex_rules
from .models import ActionDecision, ControlTarget, CycleReceipt, ReflexRule, Signal, StateObservation

__all__ = [
    "ActionDecision",
    "AudioV4Snapshot",
    "ControlTarget",
    "CycleReceipt",
    "CyberneticController",
    "ReflexRule",
    "Signal",
    "StateObservation",
    "assess_audio_v4_snapshot",
    "default_reflex_rules",
    "run_privacy_safe_canary",
]

__version__ = "11.0.0"
