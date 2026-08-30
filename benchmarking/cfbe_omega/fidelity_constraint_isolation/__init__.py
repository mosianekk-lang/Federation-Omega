"""CFBE-Omega fidelity and platform-constraint isolation kernel."""

from .core import (
    AdapterRoute,
    CanonicalSource,
    CapabilityAttestation,
    CapabilityRequirement,
    FidelityDecision,
    FidelityError,
    FidelityMode,
    InvariantKind,
    IsolationPolicy,
    MaturityEvidence,
    MaturityState,
    PlatformProfile,
    ProtectedInvariant,
    evaluate_fidelity,
    isolate_constraints,
    isolate_payload,
)

__all__ = [
    "AdapterRoute",
    "CanonicalSource",
    "CapabilityAttestation",
    "CapabilityRequirement",
    "FidelityDecision",
    "FidelityError",
    "FidelityMode",
    "InvariantKind",
    "IsolationPolicy",
    "MaturityEvidence",
    "MaturityState",
    "PlatformProfile",
    "ProtectedInvariant",
    "evaluate_fidelity",
    "isolate_constraints",
    "isolate_payload",
]
