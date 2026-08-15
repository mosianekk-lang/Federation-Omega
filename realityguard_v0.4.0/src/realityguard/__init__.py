"""RealityGuard public API."""

from .engine import RealityGuard
from .model import EvidenceGrade, LifecycleState, Verdict
from .capability import CapabilityRegistry, CapabilityState
from .solutions import ReuseAction, SolutionRouter
from .prebuild import PrebuildDecisionCode, PrebuildGate, manifest_snapshot_hash
from .upgrade import CycleKind, GovernedUpgradeEngine, UpgradeDecisionCode

__all__ = [
    "RealityGuard", "EvidenceGrade", "LifecycleState", "Verdict",
    "CapabilityRegistry", "CapabilityState", "ReuseAction", "SolutionRouter",
    "PrebuildDecisionCode", "PrebuildGate", "manifest_snapshot_hash",
    "CycleKind", "GovernedUpgradeEngine", "UpgradeDecisionCode",
]
__version__ = "0.4.0"
