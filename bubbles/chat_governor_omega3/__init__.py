"""Bubbles Adaptive Chat Governor Ω3.7.

Truth boundary: this package governs Bubbles workflows routed through it. It does
not modify hidden ChatGPT context management, provider serving infrastructure,
or connector calls that bypass this middleware. Ω3.7 binds the admitted frontier
controls into the existing ChatGov surface and makes explicit safe-read
single-flight load-bearing inside ConnectorGateway without creating authority.
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
from .continuity import (
    CommandEnvelope,
    CommandState,
    ContinuityLaneSpec,
    ContinuityLaneState,
    ContinuityReceipt,
    EffectClass,
    LaneLease,
    MultistreamContinuityFabric,
    PathRole,
    intent_sha256,
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
from .frontier_binding_v1 import (
    FrontierBindingReceipt,
    FrontierControlPlane,
    SAFE_SINGLEFLIGHT_EFFECTS,
    frontier_binding_receipt,
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
    "FrontierBindingReceipt", "FrontierControlPlane", "SAFE_SINGLEFLIGHT_EFFECTS",
    "frontier_binding_receipt",
]

__version__ = "3.7.0"
