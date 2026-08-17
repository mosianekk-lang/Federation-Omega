from .completion_witness import (
    CompletionDecision,
    CompletionObservation,
    CompletionWitnessEngine,
    ContinuationClass,
    PendingUserTask,
    TaskCompletionState,
    WitnessMode,
)
from .conversation_exhaustion import (
    ConversationExhaustionGuard,
    ConversationGuardAction,
    ConversationRiskState,
    ConversationSignals,
)
from .empirical_playbook import (
    ChatLearningEvent,
    EmpiricalPlaybookEngine,
    EmpiricalPlaybookStore,
    EvidenceTier,
    LearningSeverity,
    LearningShareScope,
    LearningState,
)
from .full_fidelity_ledger import (
    ArtifactAvailability,
    ArtifactReference,
    ConversationEvent,
    ConversationEventType,
    ConversationIdentityConflict,
    ConversationNotBound,
    ConversationRole,
    EventExecutionState,
    FullFidelityConversationLedger,
    IncompleteTranscript,
    LedgerError,
    PayloadAvailability,
    TerminalExecutionClaimError,
    TranscriptConflict,
    TranscriptGap,
    TranscriptIntegrityError,
    TranscriptIntegrityState,
    TranscriptRestoreMode,
)
from .models import (
    ApprovalState,
    ContinuationMode,
    GovernanceCapsule,
    ProviderContinuationRef,
    RestorePreviewReason,
)
from .operating_profile import OperatingProfile
from .restore_assurance import (
    RestoreAssuranceEngine,
    RestoreAttestation,
    RestoreConformanceState,
    RestoreFinding,
)
from .runtime import ChatBridgeOmega4 as ChatBridgeOmega47
from .runtime_omega48 import ChatBridgeOmega48
from .store import (
    ChatBridgeStore,
    NamespaceCollision,
    NamespaceNotFound,
)

# Package-level compatibility alias: new consumers that import ChatBridgeOmega4 from the
# package receive the current Ω4.8 runtime, while the prior Ω4.7 implementation remains
# explicitly available as ChatBridgeOmega47 and through bubbles.chatbridge_omega4.runtime.
ChatBridgeOmega4 = ChatBridgeOmega48

__all__ = [
    "ApprovalState",
    "ArtifactAvailability",
    "ArtifactReference",
    "ChatBridgeOmega4",
    "ChatBridgeOmega47",
    "ChatBridgeOmega48",
    "ChatBridgeStore",
    "ChatLearningEvent",
    "CompletionDecision",
    "CompletionObservation",
    "CompletionWitnessEngine",
    "ContinuationClass",
    "ContinuationMode",
    "ConversationEvent",
    "ConversationEventType",
    "ConversationExhaustionGuard",
    "ConversationGuardAction",
    "ConversationIdentityConflict",
    "ConversationNotBound",
    "ConversationRiskState",
    "ConversationRole",
    "ConversationSignals",
    "EmpiricalPlaybookEngine",
    "EmpiricalPlaybookStore",
    "EventExecutionState",
    "EvidenceTier",
    "FullFidelityConversationLedger",
    "GovernanceCapsule",
    "IncompleteTranscript",
    "LedgerError",
    "LearningSeverity",
    "LearningShareScope",
    "LearningState",
    "NamespaceCollision",
    "NamespaceNotFound",
    "OperatingProfile",
    "PayloadAvailability",
    "PendingUserTask",
    "ProviderContinuationRef",
    "RestoreAssuranceEngine",
    "RestoreAttestation",
    "RestoreConformanceState",
    "RestoreFinding",
    "RestorePreviewReason",
    "TaskCompletionState",
    "TerminalExecutionClaimError",
    "TranscriptConflict",
    "TranscriptGap",
    "TranscriptIntegrityError",
    "TranscriptIntegrityState",
    "TranscriptRestoreMode",
    "WitnessMode",
]
