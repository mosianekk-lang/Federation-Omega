"""Bubbles Adaptive Chat Governor Ω3.5.

Truth boundary: this package governs Bubbles workflows routed through it. It does
not modify hidden ChatGPT context management, provider serving infrastructure,
or connector calls that bypass this middleware. The continuity fabric preserves
and resumes work across host turns; it does not claim hidden/background execution.
"""

from .routing import MissionCompiler, MissionPlan, MemoryGovernor
from .runtime import ConnectorGateway
from .state import DurableState, EvidencePointer
from .dag import DAGExecutor, Lane, LaneState
from .completion import ChatGovCompletionInterlock, CompletionReconcileResult
from .provider_trust import ChatGovProviderTrustInterlock, ProviderDependencyReconcileResult
from .cognitive_precision import CognitivePrecisionKernel, RouteAssessment
from .pre_final import (
    ChatGovPreFinalInterlock,
    ClaimScanSnapshot,
    ControlBinding,
    FinalizationDecision,
    GapState,
    MissionClosureState,
    PreFinalGate,
    PreFinalReconcileResult,
    TerminalState,
)
from .regression import ObservedIntegrityIncident, RegressionCandidate, TraceToRegressionBridge
from .continuity import (
    CommandEnvelope, CommandState, ContinuityLaneSpec, ContinuityLaneState,
    ContinuityReceipt, EffectClass, LaneLease, MultistreamContinuityFabric,
    PathRole, intent_sha256,
)
from .performance_kernel import (
    DeltaCapsule,
    DeltaCapsuleCompiler,
    EfficiencyFinalDecision,
    ElasticSpecialistPlanner,
    FailureObservation,
    HookContext,
    HookDecision,
    HookEvent,
    HookReceipt,
    HookResult,
    HostBindingContract,
    InformationGainDecision,
    InformationGainStopRule,
    LifecycleHookBus,
    PendingWorkLedger,
    PendingWrite,
    PerformanceComparison,
    PerformanceKernelReceipt,
    PreFinalEfficiencyGate,
    RegressionEnvelope,
    RemainingWork,
    SemanticReadCache,
    SemanticSpan,
    SkillDefinition,
    SkillPage,
    SkillPager,
    SpecialistCandidate,
    SpecialistPlan,
    ToolSchemaCache,
    TraceToRegressionCompiler,
    UnnecessaryWorkMeter,
    WorkMetrics,
    performance_kernel_receipt,
)

__all__ = [
    "MissionCompiler", "MissionPlan", "MemoryGovernor", "ConnectorGateway",
    "DurableState", "EvidencePointer", "DAGExecutor", "Lane", "LaneState",
    "ChatGovCompletionInterlock", "CompletionReconcileResult",
    "ChatGovProviderTrustInterlock", "ProviderDependencyReconcileResult",
    "CognitivePrecisionKernel", "RouteAssessment",
    "ChatGovPreFinalInterlock", "ClaimScanSnapshot", "ControlBinding",
    "FinalizationDecision", "GapState", "MissionClosureState", "PreFinalGate",
    "PreFinalReconcileResult", "TerminalState",
    "ObservedIntegrityIncident", "RegressionCandidate", "TraceToRegressionBridge",
    "CommandEnvelope", "CommandState", "ContinuityLaneSpec", "ContinuityLaneState",
    "ContinuityReceipt", "EffectClass", "LaneLease", "MultistreamContinuityFabric",
    "PathRole", "intent_sha256",
    "DeltaCapsule", "DeltaCapsuleCompiler", "EfficiencyFinalDecision",
    "ElasticSpecialistPlanner", "FailureObservation", "HookContext", "HookDecision",
    "HookEvent", "HookReceipt", "HookResult", "HostBindingContract",
    "InformationGainDecision", "InformationGainStopRule", "LifecycleHookBus",
    "PendingWorkLedger", "PendingWrite", "PerformanceComparison",
    "PerformanceKernelReceipt", "PreFinalEfficiencyGate", "RegressionEnvelope",
    "RemainingWork", "SemanticReadCache", "SemanticSpan", "SkillDefinition",
    "SkillPage", "SkillPager", "SpecialistCandidate", "SpecialistPlan",
    "ToolSchemaCache", "TraceToRegressionCompiler", "UnnecessaryWorkMeter",
    "WorkMetrics", "performance_kernel_receipt",
]

__version__ = "3.5.0"
