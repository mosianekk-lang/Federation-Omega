"""TruthGrid fail-closed enforcement and evidentiary decision primitives."""

from .guards import Mission, MissionLockDecision, MutationIntent, TruthGridGuard, TruthGridViolation
from .writer_adapter import TruthGridWriterAdapter, WriterReceipt
from .provider_trust import (
    ProviderBoundWriterReceipt,
    TruthGridProviderStageDecision,
    TruthGridProviderTrustAdapter,
)
from .falsification import AttributionFirewallError, Hypothesis, validate_personal_attribution
from .truthstate import Assessment, EvidenceSignal, Proposition, assess
from .vnext import ClosureCandidate, CompletionVector, DecisionReadiness, TruthGridVNext, TruthState

__all__ = [
    "Mission",
    "MissionLockDecision",
    "MutationIntent",
    "TruthGridGuard",
    "TruthGridViolation",
    "TruthGridWriterAdapter",
    "WriterReceipt",
    "ProviderBoundWriterReceipt",
    "TruthGridProviderStageDecision",
    "TruthGridProviderTrustAdapter",
    "AttributionFirewallError",
    "Hypothesis",
    "validate_personal_attribution",
    "Assessment",
    "EvidenceSignal",
    "Proposition",
    "assess",
    "ClosureCandidate",
    "CompletionVector",
    "DecisionReadiness",
    "TruthGridVNext",
    "TruthState",
]
