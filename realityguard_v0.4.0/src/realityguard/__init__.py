"""RealityGuard public API."""

from .engine import RealityGuard
from .model import EvidenceGrade, LifecycleState, Verdict
from .capability import CapabilityRegistry, CapabilityState
from .solutions import ReuseAction, SolutionRouter
from .prebuild import PrebuildDecisionCode, PrebuildGate, manifest_snapshot_hash
from .upgrade import CycleKind, GovernedUpgradeEngine, UpgradeDecisionCode
from .federation_adapter import FederationUpgradeAdapter
from .faultbooks import FaultbookManager
from .faultbook import FaultBookManager, FaultRecord
from .execution_guard import EffectState, ExecutionGuard, GuardDecision, PreflightResult, request_fingerprint

__all__ = [
    "RealityGuard", "EvidenceGrade", "LifecycleState", "Verdict",
    "CapabilityRegistry", "CapabilityState", "ReuseAction", "SolutionRouter",
    "PrebuildDecisionCode", "PrebuildGate", "manifest_snapshot_hash",
    "CycleKind", "GovernedUpgradeEngine", "UpgradeDecisionCode",
    "FederationUpgradeAdapter", "FaultbookManager", "FaultBookManager", "FaultRecord",
    "EffectState", "ExecutionGuard", "GuardDecision", "PreflightResult", "request_fingerprint",
]
__version__ = "0.5.0"
