"""Bubbles Adaptive Chat Governor Ω3.6.

Truth boundary: this package governs workflows routed through it. It does not
modify hidden ChatGPT context management, provider serving infrastructure, or
connector calls that bypass this middleware. Ω3.6 adds lifecycle hooks,
owner-attention control, context isolation, capability caching, durable activity
replay boundaries, adaptive parallelism, protocol-neutral interop envelopes and
durable trace-to-regression learning without creating provider authority.
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
from .frontier_runtime import (
    ActivityDecision,
    ActivityRequest,
    AdaptiveParallelismController,
    CapabilityCatalogCache,
    ContextIsolationBroker,
    DurableActivityBoundary,
    HookContext,
    HookDispatchReceipt,
    HookEvent,
    HookOutcome,
    LifecycleHookBus,
    OwnerAttentionDecision,
    OwnerAttentionGovernor,
    OwnerSignal,
    OwnerSignalKind,
    ParallelismDecision,
    ParallelismObservation,
    StablePrefixCompiler,
    StablePrefixPlan,
)
from .interop_frontier import (
    AgentTaskEnvelope,
    CapabilityAdvertisement,
    InteropAdmissionDecision,
    MCPRequestMetadata,
    admit_agent_task,
)
from .performance_controls import (
    FenceRejected,
    FencedLedgerHead,
    HardContextCapsuleError,
    LedgerConflict,
    RecoverySnapshotError,
    assess_stream,
    build_hard_context_capsule,
    sign_recovery_snapshot,
    verify_recovery_snapshot,
)
from .regression import ObservedIntegrityIncident, RegressionCandidate, TraceToRegressionBridge

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
    "ActivityDecision", "ActivityRequest", "AdaptiveParallelismController",
    "CapabilityCatalogCache", "ContextIsolationBroker", "DurableActivityBoundary",
    "HookContext", "HookDispatchReceipt", "HookEvent", "HookOutcome", "LifecycleHookBus",
    "OwnerAttentionDecision", "OwnerAttentionGovernor", "OwnerSignal", "OwnerSignalKind",
    "ParallelismDecision", "ParallelismObservation", "StablePrefixCompiler", "StablePrefixPlan",
    "AgentTaskEnvelope", "CapabilityAdvertisement", "InteropAdmissionDecision",
    "MCPRequestMetadata", "admit_agent_task",
    "FenceRejected", "FencedLedgerHead", "HardContextCapsuleError", "LedgerConflict",
    "RecoverySnapshotError", "assess_stream", "build_hard_context_capsule",
    "sign_recovery_snapshot", "verify_recovery_snapshot",
    "ObservedIntegrityIncident", "RegressionCandidate", "TraceToRegressionBridge",
]

__version__ = "3.6.0"
