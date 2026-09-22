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


from datetime import datetime, timezone


class AdapterAvailability(str, Enum):
    CALLABLE = "CALLABLE"
    BOUND = "BOUND"
    SOURCE_ONLY = "SOURCE_ONLY"
    CONNECTOR_UNAVAILABLE = "CONNECTOR_UNAVAILABLE"
    ADMIN_DISABLED = "ADMIN_DISABLED"
    UNBOUND = "UNBOUND"


class PrivacyClass(IntEnum):
    PUBLIC = 10
    INTERNAL = 20
    CONFIDENTIAL = 30
    PRIVATE = 40
    RESTRICTED = 50


class CapabilitySurfaceState(str, Enum):
    LIVE = "LIVE"
    LIVE_PARTIAL = "LIVE_PARTIAL"
    BOUND_PARTIAL = "BOUND_PARTIAL"
    SOURCE_ONLY = "SOURCE_ONLY"
    STALE_REQUALIFICATION_REQUIRED = "STALE_REQUALIFICATION_REQUIRED"
    UNKNOWN_NOT_ABSENT = "UNKNOWN_NOT_ABSENT"
    ABSENT_AFTER_ESTATE_CENSUS = "ABSENT_AFTER_ESTATE_CENSUS"


def _instant(value: str) -> datetime:
    raw = str(value).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("CAPABILITY_CURRENTNESS_TIMESTAMP_MUST_BE_OFFSET_AWARE")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class AdapterObservation:
    adapter_id: str
    capability_id: str
    provider: str
    source_ref: str
    claim_kind: ClaimKind
    declared_maturity: Maturity
    observed_at: str
    expires_at: str
    availability: AdapterAvailability = AdapterAvailability.CALLABLE
    authority_classes: tuple[str, ...] = ()
    effect_classes: tuple[str, ...] = ("NO_EFFECT", "READ_ONLY")
    privacy_ceiling: PrivacyClass = PrivacyClass.PRIVATE
    failure_domain: str = ""
    reliability: float = 1.0
    proof_strength: float = 1.0
    monetary_cost: float = 0.0
    owner_burden: float = 0.0
    independently_verified: bool = False
    metadata: tuple[tuple[str, str], ...] = ()

    def validate(self) -> "AdapterObservation":
        if not all((
            self.adapter_id.strip(),
            self.capability_id.strip(),
            self.provider.strip(),
            self.source_ref.strip(),
            self.observed_at.strip(),
            self.expires_at.strip(),
        )):
            raise ValueError("CAPABILITY_ADAPTER_OBSERVATION_IDENTITY_REQUIRED")
        observed = _instant(self.observed_at)
        expires = _instant(self.expires_at)
        if expires <= observed:
            raise ValueError("CAPABILITY_ADAPTER_EXPIRY_INVALID")
        for value, name in (
            (self.reliability, "CAPABILITY_ADAPTER_RELIABILITY_INVALID"),
            (self.proof_strength, "CAPABILITY_ADAPTER_PROOF_STRENGTH_INVALID"),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(name)
        if self.monetary_cost < 0 or self.owner_burden < 0:
            raise ValueError("CAPABILITY_ADAPTER_COST_OR_BURDEN_INVALID")
        return self

    def fresh_at(self, now: str) -> bool:
        self.validate()
        point = _instant(now)
        return _instant(self.observed_at) <= point < _instant(self.expires_at)

    @property
    def callable_now(self) -> bool:
        return self.availability is AdapterAvailability.CALLABLE

    def to_evidence(self, *, now: str) -> EvidenceRef:
        self.validate()
        return EvidenceRef(
            evidence_id=f"adapter:{self.adapter_id}:{digest((self.source_ref, self.observed_at))[-16:]}",
            capability_id=self.capability_id,
            claim_kind=self.claim_kind,
            source_ref=self.source_ref,
            declared_maturity=self.declared_maturity,
            fresh=self.fresh_at(now),
            independently_verified=self.independently_verified,
            metadata=(
                ("adapter_id", self.adapter_id),
                ("provider", self.provider),
                ("availability", self.availability.value),
                ("failure_domain", self.failure_domain),
            ) + self.metadata,
        ).validate()


@dataclass(frozen=True, slots=True)
class CapabilityRouteRequirement:
    capability_id: str
    required_maturity: Maturity = Maturity.BOUND
    authority_class: str = ""
    effect_class: str = "NO_EFFECT"
    privacy_class: PrivacyClass = PrivacyClass.INTERNAL
    require_callable: bool = True
    require_independent_verification: bool = False
    excluded_failure_domains: tuple[str, ...] = ()

    def validate(self) -> "CapabilityRouteRequirement":
        if not self.capability_id.strip():
            raise ValueError("CAPABILITY_ROUTE_REQUIREMENT_ID_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class AdapterRouteDecision:
    adapter_id: str
    provider: str
    capability_id: str
    eligible: bool
    maturity: Maturity
    state: str
    reasons: tuple[str, ...]
    score: tuple[float, ...]

    @property
    def selected(self) -> bool:
        return self.eligible and self.state == "SELECTED"


@dataclass(frozen=True, slots=True)
class CapabilityCurrentnessSnapshot:
    capability_id: str
    state: CapabilitySurfaceState
    max_maturity: Maturity
    fresh_adapters: tuple[str, ...]
    callable_adapters: tuple[str, ...]
    selected_adapter: str = ""
    reasons: tuple[str, ...] = ()


class CapabilityCurrentnessFabric:
    """Fuse cross-estate observations into maturity/currentness-aware route decisions."""

    def __init__(self, observations: Iterable[AdapterObservation] = ()):
        self._observations: list[AdapterObservation] = []
        for observation in observations:
            self.add(observation)

    def add(self, observation: AdapterObservation) -> None:
        observation.validate()
        self._observations.append(observation)

    def observations_for(self, capability_id: str) -> tuple[AdapterObservation, ...]:
        return tuple(item for item in self._observations if item.capability_id == capability_id)

    def truth_record(self, capability_id: str, *, now: str) -> CapabilityTruthRecord | None:
        observations = self.observations_for(capability_id)
        if not observations:
            return None
        return CapabilityTruthRecord(
            capability_id,
            tuple(item.to_evidence(now=now) for item in observations),
        ).validate()

    def _route_reasons(
        self,
        observation: AdapterObservation,
        requirement: CapabilityRouteRequirement,
        *,
        now: str,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        evidence = observation.to_evidence(now=now)
        if not evidence.fresh:
            reasons.append("ADAPTER_EVIDENCE_STALE")
        if requirement.require_callable and not observation.callable_now:
            reasons.append("ADAPTER_NOT_CALLABLE")
        if evidence.admitted_maturity < requirement.required_maturity:
            reasons.append("ADAPTER_MATURITY_BELOW_REQUIREMENT")
        if requirement.require_independent_verification and not observation.independently_verified:
            reasons.append("ADAPTER_NOT_INDEPENDENTLY_VERIFIED")
        if requirement.authority_class and requirement.authority_class not in observation.authority_classes:
            reasons.append("ADAPTER_AUTHORITY_MISMATCH")
        if requirement.effect_class not in observation.effect_classes:
            reasons.append("ADAPTER_EFFECT_MISMATCH")
        if requirement.privacy_class > observation.privacy_ceiling:
            reasons.append("ADAPTER_PRIVACY_MISMATCH")
        if observation.failure_domain and observation.failure_domain in requirement.excluded_failure_domains:
            reasons.append("ADAPTER_FAILURE_DOMAIN_EXCLUDED")
        return tuple(reasons)

    def rank(
        self,
        requirement: CapabilityRouteRequirement,
        *,
        now: str,
    ) -> tuple[AdapterRouteDecision, ...]:
        requirement.validate()
        decisions: list[AdapterRouteDecision] = []
        for observation in self.observations_for(requirement.capability_id):
            reasons = self._route_reasons(observation, requirement, now=now)
            evidence = observation.to_evidence(now=now)
            eligible = not reasons
            score = (
                float(evidence.admitted_maturity),
                1.0 if observation.independently_verified else 0.0,
                float(observation.proof_strength),
                float(observation.reliability),
                -float(observation.owner_burden),
                -float(observation.monetary_cost),
            )
            decisions.append(
                AdapterRouteDecision(
                    observation.adapter_id,
                    observation.provider,
                    observation.capability_id,
                    eligible,
                    evidence.admitted_maturity,
                    "ELIGIBLE" if eligible else "INELIGIBLE",
                    reasons,
                    score,
                )
            )
        decisions.sort(key=lambda item: (item.eligible, item.score, item.adapter_id), reverse=True)
        if decisions and decisions[0].eligible:
            first = decisions[0]
            decisions[0] = AdapterRouteDecision(
                first.adapter_id,
                first.provider,
                first.capability_id,
                first.eligible,
                first.maturity,
                "SELECTED",
                first.reasons,
                first.score,
            )
        return tuple(decisions)

    def snapshot(
        self,
        capability_id: str,
        *,
        now: str,
        requirement: CapabilityRouteRequirement | None = None,
        census_complete: bool = False,
    ) -> CapabilityCurrentnessSnapshot:
        observations = self.observations_for(capability_id)
        if not observations:
            return CapabilityCurrentnessSnapshot(
                capability_id,
                CapabilitySurfaceState.ABSENT_AFTER_ESTATE_CENSUS if census_complete else CapabilitySurfaceState.UNKNOWN_NOT_ABSENT,
                Maturity.SPECIFIED,
                (),
                (),
                reasons=("NO_OBSERVATIONS",),
            )

        record = self.truth_record(capability_id, now=now)
        assert record is not None
        fresh = tuple(sorted(item.adapter_id for item in observations if item.fresh_at(now)))
        callable_adapters = tuple(sorted(item.adapter_id for item in observations if item.fresh_at(now) and item.callable_now))
        max_maturity = record.max_proven_maturity

        selected = ""
        if requirement is not None:
            ranked = self.rank(requirement, now=now)
            selected = next((item.adapter_id for item in ranked if item.selected), "")

        if not fresh:
            state = CapabilitySurfaceState.STALE_REQUALIFICATION_REQUIRED
        elif callable_adapters and max_maturity >= Maturity.PROVIDER_READBACK:
            state = CapabilitySurfaceState.LIVE
        elif callable_adapters and max_maturity >= Maturity.BOUND:
            state = CapabilitySurfaceState.LIVE_PARTIAL
        elif max_maturity >= Maturity.BOUND:
            state = CapabilitySurfaceState.BOUND_PARTIAL
        elif max_maturity >= Maturity.BUILT:
            state = CapabilitySurfaceState.SOURCE_ONLY
        else:
            state = CapabilitySurfaceState.UNKNOWN_NOT_ABSENT

        return CapabilityCurrentnessSnapshot(
            capability_id,
            state,
            max_maturity,
            fresh,
            callable_adapters,
            selected_adapter=selected,
            reasons=("CURRENTNESS_FUSED",),
        )


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
