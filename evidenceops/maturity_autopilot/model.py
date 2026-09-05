from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable


class MaturityLevel(IntEnum):
    M0_CONCEPT = 0
    M1_SPECIFIED = 1
    M2_IMPLEMENTED = 2
    M3_TESTED = 3
    M4_INTEGRATED = 4
    M5_BOUNDED_RUNTIME = 5
    M6_PROVIDER_VERIFIED = 6
    M7_RESILIENT = 7
    M8_REAL_WORKFLOW_CALIBRATED = 8
    M9_OPERATIONAL = 9
    M10_PRODUCTION_ASSURED = 10
    M11_CONTINUOUSLY_CERTIFIED = 11


@dataclass(frozen=True)
class EvidenceGate:
    gate_id: str
    min_level: MaturityLevel
    proof_type: str
    required: bool = True


DEFAULT_GATES: tuple[EvidenceGate, ...] = (
    EvidenceGate("spec", MaturityLevel.M1_SPECIFIED, "versioned specification"),
    EvidenceGate("source", MaturityLevel.M2_IMPLEMENTED, "admitted source or immutable implementation artefact"),
    EvidenceGate("tests", MaturityLevel.M3_TESTED, "deterministic regression evidence"),
    EvidenceGate("integration", MaturityLevel.M4_INTEGRATED, "cross-component integration evidence"),
    EvidenceGate("runtime", MaturityLevel.M5_BOUNDED_RUNTIME, "bounded live/runtime execution receipt"),
    EvidenceGate("provider_readback", MaturityLevel.M6_PROVIDER_VERIFIED, "target-specific provider-native readback"),
    EvidenceGate("rollback", MaturityLevel.M7_RESILIENT, "failure injection, recovery and rollback proof"),
    EvidenceGate("workflow_calibration", MaturityLevel.M8_REAL_WORKFLOW_CALIBRATED, "representative workflow calibration evidence"),
    EvidenceGate("slo", MaturityLevel.M9_OPERATIONAL, "observability, SLO and operating evidence"),
    EvidenceGate("security_privacy", MaturityLevel.M10_PRODUCTION_ASSURED, "security, privacy, DR and consequential-governance evidence"),
    EvidenceGate("recertification", MaturityLevel.M11_CONTINUOUSLY_CERTIFIED, "current periodic recertification with expiry/drift controls"),
)


@dataclass
class CapabilityEvidence:
    capability_id: str
    claimed_level: MaturityLevel
    proofs: dict[str, bool] = field(default_factory=dict)
    blocked_external: bool = False
    blocker: str | None = None
    retired: bool = False

    def derived_level(self, gates: Iterable[EvidenceGate] = DEFAULT_GATES) -> MaturityLevel:
        if self.retired:
            return MaturityLevel.M0_CONCEPT
        achieved = MaturityLevel.M0_CONCEPT
        for gate in sorted(gates, key=lambda g: int(g.min_level)):
            if gate.required and not self.proofs.get(gate.gate_id, False):
                break
            achieved = gate.min_level
        return achieved

    def drifted(self) -> bool:
        return self.claimed_level > self.derived_level()

    def next_missing_gate(self, gates: Iterable[EvidenceGate] = DEFAULT_GATES) -> EvidenceGate | None:
        current = self.derived_level(gates)
        for gate in sorted(gates, key=lambda g: int(g.min_level)):
            if gate.min_level > current and not self.proofs.get(gate.gate_id, False):
                return gate
        return None
