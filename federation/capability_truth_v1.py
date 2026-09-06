"""FUSE Capability Truth Core v1.

This module prevents descriptive/specification material from being consumed as
runtime capability proof. It is provider-neutral and effect-free.

Core laws:
- a claim cannot prove maturity above the ceiling of its claim kind;
- propagation cannot increase source maturity;
- mission eligibility requires current proven maturity >= required maturity;
- registration, documentation and model memory never prove runtime execution.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, IntEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping

SCHEMA = "FUSE-CAPABILITY-TRUTH-V1"
VERSION = "1.0.0"


class Maturity(IntEnum):
    SPECIFIED = 10
    DESIGNED = 20
    BUILT = 30
    TESTED_LOCAL = 40
    SOURCE_ADMITTED = 50
    CI_ADMITTED = 60
    BOUND = 70
    HOSTED = 80
    PROVIDER_RUNNING = 90
    PROVIDER_READBACK = 100
    BEHAVIOUR_VERIFIED = 110
    VALUE_PROVEN = 120


class ClaimKind(str, Enum):
    REQUIREMENT = "REQUIREMENT"
    DESIGN = "DESIGN"
    ROLE_REGISTRATION = "ROLE_REGISTRATION"
    IMPLEMENTATION = "IMPLEMENTATION"
    TEST_RESULT = "TEST_RESULT"
    SOURCE_ADMISSION = "SOURCE_ADMISSION"
    CI_ADMISSION = "CI_ADMISSION"
    BINDING = "BINDING"
    HOST_RECEIPT = "HOST_RECEIPT"
    RUNTIME_RECEIPT = "RUNTIME_RECEIPT"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    BEHAVIOURAL_EVIDENCE = "BEHAVIOURAL_EVIDENCE"
    VALUE_EVIDENCE = "VALUE_EVIDENCE"
    NARRATIVE_SUMMARY = "NARRATIVE_SUMMARY"
    MODEL_MEMORY = "MODEL_MEMORY"
    REGISTRY_LABEL = "REGISTRY_LABEL"


CLAIM_CEILING: Mapping[ClaimKind, Maturity] = {
    ClaimKind.REQUIREMENT: Maturity.SPECIFIED,
    ClaimKind.DESIGN: Maturity.DESIGNED,
    ClaimKind.ROLE_REGISTRATION: Maturity.DESIGNED,
    ClaimKind.IMPLEMENTATION: Maturity.BUILT,
    ClaimKind.TEST_RESULT: Maturity.TESTED_LOCAL,
    ClaimKind.SOURCE_ADMISSION: Maturity.SOURCE_ADMITTED,
    ClaimKind.CI_ADMISSION: Maturity.CI_ADMITTED,
    ClaimKind.BINDING: Maturity.BOUND,
    ClaimKind.HOST_RECEIPT: Maturity.HOSTED,
    ClaimKind.RUNTIME_RECEIPT: Maturity.PROVIDER_RUNNING,
    ClaimKind.PROVIDER_READBACK: Maturity.PROVIDER_READBACK,
    ClaimKind.BEHAVIOURAL_EVIDENCE: Maturity.BEHAVIOUR_VERIFIED,
    ClaimKind.VALUE_EVIDENCE: Maturity.VALUE_PROVEN,
    ClaimKind.NARRATIVE_SUMMARY: Maturity.SPECIFIED,
    ClaimKind.MODEL_MEMORY: Maturity.SPECIFIED,
    ClaimKind.REGISTRY_LABEL: Maturity.SPECIFIED,
}


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(value: object) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    capability_id: str
    claim_kind: ClaimKind
    source_ref: str
    declared_maturity: Maturity = Maturity.SPECIFIED
    source_maturity: Maturity | None = None
    fresh: bool = True
    independently_verified: bool = False
    metadata: tuple[tuple[str, str], ...] = ()

    def validate(self) -> "EvidenceRef":
        if not self.evidence_id.strip() or not self.capability_id.strip() or not self.source_ref.strip():
            raise ValueError("CAPABILITY_EVIDENCE_IDENTITY_REQUIRED")
        if self.source_maturity is not None and self.declared_maturity > self.source_maturity:
            raise ValueError("PROPAGATED_MATURITY_EXCEEDS_SOURCE")
        return self

    @property
    def admitted_maturity(self) -> Maturity:
        self.validate()
        ceiling = CLAIM_CEILING[self.claim_kind]
        maturity = min(self.declared_maturity, ceiling)
        if self.source_maturity is not None:
            maturity = min(maturity, self.source_maturity)
        return Maturity(maturity)

    @property
    def fingerprint(self) -> str:
        return digest(
            {
                "evidence_id": self.evidence_id,
                "capability_id": self.capability_id,
                "claim_kind": self.claim_kind.value,
                "source_ref": self.source_ref,
                "declared_maturity": int(self.declared_maturity),
                "source_maturity": None if self.source_maturity is None else int(self.source_maturity),
                "fresh": self.fresh,
                "independently_verified": self.independently_verified,
                "metadata": self.metadata,
            }
        )


def propagate_evidence(
    source: EvidenceRef,
    *,
    evidence_id: str,
    source_ref: str,
    claim_kind: ClaimKind = ClaimKind.NARRATIVE_SUMMARY,
    declared_maturity: Maturity | None = None,
) -> EvidenceRef:
    """Create a downstream claim that can never exceed source admitted maturity."""
    source.validate()
    source_proven = source.admitted_maturity
    requested = declared_maturity or source_proven
    requested = Maturity(min(requested, source_proven))
    return EvidenceRef(
        evidence_id=evidence_id,
        capability_id=source.capability_id,
        claim_kind=claim_kind,
        source_ref=source_ref,
        declared_maturity=requested,
        source_maturity=source_proven,
        fresh=source.fresh,
        independently_verified=False,
        metadata=(("derived_from", source.evidence_id), ("source_fingerprint", source.fingerprint)),
    )


@dataclass(frozen=True, slots=True)
class CapabilityTruthRecord:
    capability_id: str
    evidence: tuple[EvidenceRef, ...] = ()
    revoked: bool = False
    revocation_reason: str = ""

    def validate(self) -> "CapabilityTruthRecord":
        if not self.capability_id.strip():
            raise ValueError("CAPABILITY_ID_REQUIRED")
        ids: set[str] = set()
        for item in self.evidence:
            item.validate()
            if item.capability_id != self.capability_id:
                raise ValueError("CAPABILITY_EVIDENCE_SUBJECT_MISMATCH")
            if item.evidence_id in ids:
                raise ValueError("DUPLICATE_CAPABILITY_EVIDENCE_ID")
            ids.add(item.evidence_id)
        return self

    @property
    def max_proven_maturity(self) -> Maturity:
        self.validate()
        if self.revoked:
            return Maturity.SPECIFIED
        eligible = [item.admitted_maturity for item in self.evidence if item.fresh]
        return max(eligible, default=Maturity.SPECIFIED)

    def add(self, *items: EvidenceRef) -> "CapabilityTruthRecord":
        return replace(self, evidence=self.evidence + tuple(items)).validate()

    def revoke(self, reason: str) -> "CapabilityTruthRecord":
        if not str(reason).strip():
            raise ValueError("CAPABILITY_REVOCATION_REASON_REQUIRED")
        return replace(self, revoked=True, revocation_reason=str(reason).strip())


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    capability_id: str
    required_maturity: Maturity
    require_fresh: bool = True
    require_independent_verification: bool = False

    def validate(self) -> "CapabilityRequirement":
        if not self.capability_id.strip():
            raise ValueError("CAPABILITY_REQUIREMENT_ID_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    capability_id: str
    state: str
    required_maturity: Maturity
    proven_maturity: Maturity
    reasons: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return self.state == "ELIGIBLE"


class CapabilityEligibilityCourt:
    """Fail-closed capability gate for mission planning."""

    def decide(
        self,
        requirement: CapabilityRequirement,
        record: CapabilityTruthRecord | None,
    ) -> EligibilityDecision:
        requirement.validate()
        if record is None:
            return EligibilityDecision(
                requirement.capability_id,
                "INELIGIBLE",
                requirement.required_maturity,
                Maturity.SPECIFIED,
                ("NO_CAPABILITY_TRUTH_RECORD",),
            )
        record.validate()
        if record.capability_id != requirement.capability_id:
            raise ValueError("CAPABILITY_REQUIREMENT_RECORD_MISMATCH")
        if record.revoked:
            return EligibilityDecision(
                record.capability_id,
                "INELIGIBLE",
                requirement.required_maturity,
                Maturity.SPECIFIED,
                ("CAPABILITY_REVOKED", record.revocation_reason),
            )
        evidence = list(record.evidence)
        if requirement.require_fresh:
            evidence = [item for item in evidence if item.fresh]
        if requirement.require_independent_verification:
            evidence = [item for item in evidence if item.independently_verified]
        proven = max((item.admitted_maturity for item in evidence), default=Maturity.SPECIFIED)
        if proven < requirement.required_maturity:
            return EligibilityDecision(
                record.capability_id,
                "INELIGIBLE",
                requirement.required_maturity,
                Maturity(proven),
                ("PROVEN_MATURITY_BELOW_REQUIREMENT",),
            )
        return EligibilityDecision(
            record.capability_id,
            "ELIGIBLE",
            requirement.required_maturity,
            Maturity(proven),
            ("REQUIRED_MATURITY_PROVEN",),
        )


def capability_truth_index(records: Iterable[CapabilityTruthRecord]) -> dict[str, Maturity]:
    result: dict[str, Maturity] = {}
    for record in records:
        record.validate()
        if record.capability_id in result:
            raise ValueError("DUPLICATE_CAPABILITY_TRUTH_RECORD")
        result[record.capability_id] = record.max_proven_maturity
    return result


__all__ = [
    "SCHEMA",
    "VERSION",
    "CLAIM_CEILING",
    "CapabilityEligibilityCourt",
    "CapabilityRequirement",
    "CapabilityTruthRecord",
    "ClaimKind",
    "EligibilityDecision",
    "EvidenceRef",
    "Maturity",
    "capability_truth_index",
    "digest",
    "propagate_evidence",
]
