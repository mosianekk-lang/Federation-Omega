from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
import hashlib
import json
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class EvidenceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    CORROBORATED = "CORROBORATED"
    USER_SUPPLIED = "USER_SUPPLIED"
    INFERENCE = "INFERENCE"
    MODEL_ESTIMATE = "MODEL_ESTIMATE"
    UNVERIFIED = "UNVERIFIED"


class InformationClass(str, Enum):
    PUBLIC = "PUBLIC"
    CONFIDENTIAL = "CONFIDENTIAL"
    CLEAN_TEAM = "CLEAN_TEAM"
    POTENTIALLY_MNPI = "POTENTIALLY_MNPI"
    RESTRICTED = "RESTRICTED"
    PRIVILEGED = "PRIVILEGED"
    UNKNOWN = "UNKNOWN"


class Domain(str, Enum):
    PRIVATE_MNA = "PRIVATE_MNA"
    PUBLIC_MARKETS = "PUBLIC_MARKETS"
    PORTFOLIO = "PORTFOLIO"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"
    GOVERNANCE = "GOVERNANCE"


class AuthorityLevel(str, Enum):
    A0_MANUAL = "A0_MANUAL"
    A1_ASSISTED = "A1_ASSISTED"
    A2_PREPARED = "A2_PREPARED"
    A3_SUPERVISED_AUTOMATION = "A3_SUPERVISED_AUTOMATION"
    A4_BOUNDED_AUTONOMY = "A4_BOUNDED_AUTONOMY"
    A5_SOVEREIGN_AUTHORITY = "A5_SOVEREIGN_AUTHORITY"


class ActionDisposition(str, Enum):
    ALLOW_INTERNAL = "ALLOW_INTERNAL"
    ALLOW_LOGGED = "ALLOW_LOGGED"
    REQUIRE_HUMAN = "REQUIRE_HUMAN"
    DENY = "DENY"


class MaturityState(str, Enum):
    DESIGNED = "DESIGNED"
    PROTOTYPED = "PROTOTYPED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    DEPLOYED = "DEPLOYED"
    PRODUCTION_VERIFIED = "PRODUCTION_VERIFIED"


@dataclass(frozen=True)
class EvidenceRef:
    source_id: str
    source_type: str
    locator: str
    observed_at: str = field(default_factory=utc_now_iso)
    content_hash: str | None = None
    authority: str | None = None

    def fingerprint(self) -> str:
        return stable_sha256(asdict(self))


@dataclass
class Claim:
    subject_id: str
    predicate: str
    value: Any
    status: EvidenceStatus
    evidence: list[EvidenceRef] = field(default_factory=list)
    information_class: InformationClass = InformationClass.UNKNOWN
    domain: Domain = Domain.PRIVATE_MNA
    confidence: float = 0.0
    assumptions: list[str] = field(default_factory=list)
    supersedes: str | None = None
    claim_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now_iso)

    def validate(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.status in {EvidenceStatus.VERIFIED, EvidenceStatus.CORROBORATED} and not self.evidence:
            raise ValueError(f"{self.status.value} claims require source evidence")
        if self.status == EvidenceStatus.MODEL_ESTIMATE and not self.assumptions:
            raise ValueError("MODEL_ESTIMATE claims require explicit assumptions")
        if not self.subject_id or not self.predicate:
            raise ValueError("subject_id and predicate are required")

    def normalized_value(self) -> str:
        return canonical_json(self.value)

    def fingerprint(self) -> str:
        payload = {
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "value": self.value,
            "status": self.status.value,
            "evidence": [asdict(e) for e in self.evidence],
            "information_class": self.information_class.value,
            "domain": self.domain.value,
            "confidence": self.confidence,
            "assumptions": self.assumptions,
            "supersedes": self.supersedes,
        }
        return stable_sha256(payload)


@dataclass
class Event:
    event_type: str
    source: str
    subject_id: str
    payload: Mapping[str, Any]
    domain: Domain
    information_class: InformationClass
    materiality: float = 0.0
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=utc_now_iso)

    def validate(self) -> None:
        if not self.event_type or not self.source or not self.subject_id:
            raise ValueError("event_type, source and subject_id are required")
        if not 0 <= self.materiality <= 1:
            raise ValueError("materiality must be between 0 and 1")


@dataclass(frozen=True)
class ActionRequest:
    action_type: str
    source_domain: Domain
    target_domain: Domain
    information_class: InformationClass
    reversible: bool = True
    external_effect: bool = False
    financial_effect: bool = False
    destructive: bool = False
    requested_authority: AuthorityLevel = AuthorityLevel.A1_ASSISTED
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionDecision:
    disposition: ActionDisposition
    reason_codes: tuple[str, ...]
    required_authority: AuthorityLevel


@dataclass
class DecisionPassport:
    decision_id: str
    proposition: str
    evidence_claim_ids: list[str]
    assumptions: list[str]
    alternatives: list[str]
    confidence: float
    dissent: list[str]
    decided_by: str | None = None
    status: str = "PREPARED"
    created_at: str = field(default_factory=utc_now_iso)

    def digest(self) -> str:
        return stable_sha256(asdict(self))


@dataclass(frozen=True)
class CapitalCandidate:
    candidate_id: str
    expected_value: float
    confidence: float
    strategic_fit: float
    optionality: float
    risk: float
    capital_intensity: float
    time_burden: float
    complexity: float
    opportunity_cost: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        for name in (
            "confidence", "strategic_fit", "optionality", "risk",
            "capital_intensity", "time_burden", "complexity", "opportunity_cost",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class RankedCandidate:
    candidate_id: str
    score: float
    expected_value: float
    rank: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    category: str
    priority: float
    message: str
    subject_id: str
    requires_human: bool
    reason_codes: list[str] = field(default_factory=list)


@dataclass
class AutopilotResult:
    event_id: str
    claim_ids: list[str]
    contradiction_ids: list[str]
    impacted_subjects: list[str]
    alerts: list[Alert]
    action_decisions: list[ActionDecision]
    learning_event_hash: str
    state: str = "SUCCESS"
