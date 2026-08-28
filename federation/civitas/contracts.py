from __future__ import annotations

"""Typed contracts for Federation Ω CIVITAS.

The package is deliberately provider-neutral and effect-free. It can describe,
rank, simulate, and prepare internal changes, but it cannot manufacture provider
identity, credentials, external authority, or completion proof.
"""

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA = "FEDERATION-OMEGA-CIVITAS-SUITE-V1"
VERSION = "1.0.0"
AUTHORITY_CEILING = "A1_INTERNAL"
EXTERNAL_EFFECTS = 0

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:/@-]{1,256}$")
_SECRET_KEYS = {
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "authorization", "cookie", "access_key", "client_secret",
}
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}", re.I),
)


class CivitasError(RuntimeError):
    """Fail-closed domain error."""


class ProofLevel(str, Enum):
    UNKNOWN = "UNKNOWN"
    DECLARED = "DECLARED"
    SOURCE_READBACK = "SOURCE_READBACK"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    SHADOW_VERIFIED = "SHADOW_VERIFIED"
    RUNTIME_READBACK = "RUNTIME_READBACK"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"


PROOF_RANK = {
    ProofLevel.UNKNOWN: 0,
    ProofLevel.DECLARED: 1,
    ProofLevel.SOURCE_READBACK: 2,
    ProofLevel.DETERMINISTIC_TESTED: 3,
    ProofLevel.SHADOW_VERIFIED: 4,
    ProofLevel.RUNTIME_READBACK: 5,
    ProofLevel.PROVIDER_READBACK: 6,
    ProofLevel.RECEIPT_VERIFIED: 7,
}


class MaturityStage(str, Enum):
    DESIGN = "DESIGN"
    SOURCE_READY = "SOURCE_READY"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    SHADOW_VERIFIED = "SHADOW_VERIFIED"
    RUNTIME_READBACK = "RUNTIME_READBACK"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    OPERATIONAL = "OPERATIONAL"
    RESILIENT = "RESILIENT"
    FULLY_ESTABLISHED = "FULLY_ESTABLISHED"


MATURITY_RANK = {stage: index for index, stage in enumerate(MaturityStage)}


class AuthorityClass(str, Enum):
    A0_READ = "A0_READ"
    A1_INTERNAL = "A1_INTERNAL"
    A2_EFFECT = "A2_EFFECT"
    A3_DESTRUCTIVE = "A3_DESTRUCTIVE"


AUTHORITY_RANK = {
    AuthorityClass.A0_READ: 0,
    AuthorityClass.A1_INTERNAL: 1,
    AuthorityClass.A2_EFFECT: 2,
    AuthorityClass.A3_DESTRUCTIVE: 3,
}


class DecisionDisposition(str, Enum):
    SELECT = "SELECT"
    SHADOW = "SHADOW"
    HOLD = "HOLD"
    REJECT = "REJECT"
    OWNER_DECISION_REQUIRED = "OWNER_DECISION_REQUIRED"


class VoteState(str, Enum):
    PASS = "PASS"
    HOLD = "HOLD"
    VETO = "VETO"
    ABSTAIN = "ABSTAIN"


def _canonical(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def safe_id(value: str, field_name: str = "id") -> str:
    value = str(value)
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"invalid {field_name}: {value!r}")
    return value


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def in_unit_interval(value: float, field_name: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be in [0,1]")
    return value


def contains_secret_shape(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SECRET_KEYS or any(
                fragment in normalized
                for fragment in ("password", "private_key", "client_secret")
            ):
                return True
            if contains_secret_shape(nested):
                return True
        return False
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_secret_shape(item) for item in value)
    text = str(value)
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def proof_at_least(actual: ProofLevel, required: ProofLevel) -> bool:
    return PROOF_RANK[ProofLevel(actual)] >= PROOF_RANK[ProofLevel(required)]


def maturity_at_most(actual: MaturityStage, ceiling: MaturityStage) -> bool:
    return MATURITY_RANK[MaturityStage(actual)] <= MATURITY_RANK[MaturityStage(ceiling)]


def authority_at_most(actual: AuthorityClass, ceiling: AuthorityClass) -> bool:
    return AUTHORITY_RANK[AuthorityClass(actual)] <= AUTHORITY_RANK[AuthorityClass(ceiling)]


@dataclass(frozen=True)
class ProofRef:
    source_ref: str
    proof_ref: str
    observed_at: str
    level: ProofLevel
    confidence: float = 0.5
    ttl_seconds: int = 3600
    independent_source: str = "UNKNOWN"
    matter_scope: str = "GLOBAL"
    sensitivity: str = "PUBLIC_SAFE"
    authority_ceiling: AuthorityClass = AuthorityClass.A1_INTERNAL

    def validate(self) -> "ProofRef":
        if not self.source_ref.strip() or not self.observed_at.strip():
            raise ValueError("source_ref and observed_at are required")
        parse_time(self.observed_at)
        if self.level != ProofLevel.UNKNOWN and not self.proof_ref.strip():
            raise ValueError("non-unknown proof requires proof_ref")
        in_unit_interval(self.confidence, "confidence")
        if self.ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if not self.independent_source.strip() or not self.matter_scope.strip():
            raise ValueError("independent_source and matter_scope required")
        if self.sensitivity not in {"PUBLIC_SAFE", "PRIVATE_LOCAL", "P1", "P2", "P3", "P4"}:
            raise ValueError("unsupported sensitivity")
        if not authority_at_most(self.authority_ceiling, AuthorityClass.A1_INTERNAL):
            raise CivitasError("proof reference cannot expand authority")
        return self

    def fresh_at(self, now: str) -> bool:
        self.validate()
        age = max(0.0, (parse_time(now) - parse_time(self.observed_at)).total_seconds())
        return age <= self.ttl_seconds

    @property
    def rank(self) -> int:
        return PROOF_RANK[self.level]


@dataclass(frozen=True)
class ObjectiveVector:
    mission_value: float
    urgency: float
    compounding_leverage: float
    information_gain: float
    dependency_unlock: float
    confidence: float
    cost: float
    risk: float
    owner_burden: float
    reversibility: float
    horizon: str = "OPERATIONAL"

    def validate(self) -> "ObjectiveVector":
        for name in (
            "mission_value", "urgency", "compounding_leverage", "information_gain",
            "dependency_unlock", "confidence", "cost", "risk", "owner_burden",
            "reversibility",
        ):
            in_unit_interval(getattr(self, name), name)
        if self.horizon not in {"REFLEX", "OPERATIONAL", "TACTICAL", "STRATEGIC", "EVOLUTIONARY"}:
            raise ValueError("unsupported horizon")
        return self

    @property
    def utility(self) -> float:
        self.validate()
        benefit = (
            0.23 * self.mission_value
            + 0.12 * self.urgency
            + 0.20 * self.compounding_leverage
            + 0.15 * self.information_gain
            + 0.15 * self.dependency_unlock
            + 0.10 * self.confidence
            + 0.05 * self.reversibility
        )
        penalty = 0.12 * self.cost + 0.14 * self.risk + 0.12 * self.owner_burden
        return round(max(0.0, benefit - penalty), 8)

    @property
    def benefit_tuple(self) -> tuple[float, ...]:
        return (
            self.mission_value,
            self.urgency,
            self.compounding_leverage,
            self.information_gain,
            self.dependency_unlock,
            self.confidence,
            self.reversibility,
        )

    @property
    def cost_tuple(self) -> tuple[float, ...]:
        return (self.cost, self.risk, self.owner_burden)


@dataclass(frozen=True)
class ResourceBudget:
    compute: float
    tokens: float
    money: float
    latency: float
    owner_attention: float
    proof_effort: float
    storage: float
    reserve_fraction: float = 0.10

    def validate(self) -> "ResourceBudget":
        for name in ("compute", "tokens", "money", "latency", "owner_attention", "proof_effort", "storage"):
            if float(getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")
        if not 0 <= self.reserve_fraction < 1:
            raise ValueError("reserve_fraction must be in [0,1)")
        return self

    def available(self) -> "ResourceBudget":
        self.validate()
        multiplier = 1.0 - self.reserve_fraction
        return ResourceBudget(
            compute=self.compute * multiplier,
            tokens=self.tokens * multiplier,
            money=self.money * multiplier,
            latency=self.latency * multiplier,
            owner_attention=self.owner_attention * multiplier,
            proof_effort=self.proof_effort * multiplier,
            storage=self.storage * multiplier,
            reserve_fraction=0.0,
        )


@dataclass(frozen=True)
class ResourceDemand:
    compute: float = 0.0
    tokens: float = 0.0
    money: float = 0.0
    latency: float = 0.0
    owner_attention: float = 0.0
    proof_effort: float = 0.0
    storage: float = 0.0

    def validate(self) -> "ResourceDemand":
        for name in ("compute", "tokens", "money", "latency", "owner_attention", "proof_effort", "storage"):
            if float(getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")
        return self

    def as_tuple(self) -> tuple[float, ...]:
        self.validate()
        return (
            self.compute,
            self.tokens,
            self.money,
            self.latency,
            self.owner_attention,
            self.proof_effort,
            self.storage,
        )


@dataclass(frozen=True)
class FitnessVector:
    truth: float
    proof: float
    safety: float
    privacy: float
    owner_control: float
    continuity: float
    quality: float
    resilience: float
    cost_efficiency: float
    latency_efficiency: float
    owner_load: float
    learning: float
    complexity: float

    def validate(self) -> "FitnessVector":
        for name in self.__dataclass_fields__:
            in_unit_interval(getattr(self, name), name)
        return self

    @property
    def hard_veto_pass(self) -> bool:
        self.validate()
        return min(self.truth, self.proof, self.safety, self.privacy, self.owner_control) >= 0.70

    @property
    def harmonic_score(self) -> float:
        self.validate()
        values = (
            self.truth, self.proof, self.safety, self.privacy, self.owner_control,
            self.continuity, self.quality, self.resilience, self.cost_efficiency,
            self.latency_efficiency, self.owner_load, self.learning,
            max(1e-6, 1.0 - self.complexity),
        )
        return round(len(values) / sum(1.0 / max(1e-6, value) for value in values), 8)


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str
    role: str
    tags: tuple[str, ...]
    proof: ProofRef
    authority: AuthorityClass = AuthorityClass.A1_INTERNAL
    privacy_ceiling: str = "PUBLIC_SAFE"
    failure_domains: tuple[str, ...] = ()
    estimated_cost: float = 0.0
    estimated_latency: float = 0.0
    reliability: float = 0.5
    reversible: bool = True
    provider_effect: bool = False

    def validate(self) -> "CapabilityDescriptor":
        safe_id(self.capability_id, "capability_id")
        if not self.role.strip() or not self.tags:
            raise ValueError("capability role and tags required")
        self.proof.validate()
        if not authority_at_most(self.authority, AuthorityClass.A1_INTERNAL):
            raise CivitasError("capability descriptor exceeds internal authority ceiling")
        if min(self.estimated_cost, self.estimated_latency) < 0:
            raise ValueError("cost and latency cannot be negative")
        in_unit_interval(self.reliability, "reliability")
        if self.provider_effect:
            raise CivitasError("CIVITAS capability descriptors cannot execute provider effects")
        return self


@dataclass(frozen=True)
class AssuranceVote:
    voter_id: str
    institutional_role: str
    state: VoteState
    proof_refs: tuple[str, ...]
    rationale: str
    independent: bool = True
    executor_identity: bool = False

    def validate(self) -> "AssuranceVote":
        safe_id(self.voter_id, "voter_id")
        if not self.institutional_role.strip() or not self.rationale.strip():
            raise ValueError("institutional_role and rationale required")
        if self.state != VoteState.ABSTAIN and not self.proof_refs:
            raise ValueError("non-abstain vote requires proof")
        return self


@dataclass(frozen=True)
class MaturityEvidence:
    service_id: str
    claimed_stage: MaturityStage
    proof_refs: tuple[ProofRef, ...]
    tests_passed: bool = False
    shadow_passed: bool = False
    runtime_readback: bool = False
    provider_readback: bool = False
    rollback_passed: bool = False
    resilience_passed: bool = False
    independent_assurance: bool = False
    sustained_soak: bool = False

    def validate(self) -> "MaturityEvidence":
        safe_id(self.service_id, "service_id")
        if not self.proof_refs:
            raise ValueError("maturity evidence requires proof references")
        for ref in self.proof_refs:
            ref.validate()
        return self

    def highest_justified_stage(self) -> MaturityStage:
        self.validate()
        highest = MaturityStage.DESIGN
        if any(proof_at_least(ref.level, ProofLevel.SOURCE_READBACK) for ref in self.proof_refs):
            highest = MaturityStage.SOURCE_READY
        if self.tests_passed and any(
            proof_at_least(ref.level, ProofLevel.DETERMINISTIC_TESTED)
            for ref in self.proof_refs
        ):
            highest = MaturityStage.DETERMINISTIC_TESTED
        if self.shadow_passed and self.independent_assurance:
            highest = MaturityStage.SHADOW_VERIFIED
        if self.runtime_readback:
            highest = MaturityStage.RUNTIME_READBACK
        if self.provider_readback:
            highest = MaturityStage.PROVIDER_READBACK
        if self.provider_readback and self.rollback_passed and self.independent_assurance:
            highest = MaturityStage.OPERATIONAL
        if highest == MaturityStage.OPERATIONAL and self.resilience_passed:
            highest = MaturityStage.RESILIENT
        if highest == MaturityStage.RESILIENT and self.sustained_soak:
            highest = MaturityStage.FULLY_ESTABLISHED
        return highest

    def assert_no_inflation(self) -> MaturityStage:
        justified = self.highest_justified_stage()
        if MATURITY_RANK[self.claimed_stage] > MATURITY_RANK[justified]:
            raise CivitasError(
                f"maturity inflation blocked for {self.service_id}: "
                f"claimed={self.claimed_stage.value} justified={justified.value}"
            )
        return justified


@dataclass(frozen=True)
class DecisionReceipt:
    decision_id: str
    disposition: DecisionDisposition
    selected_ids: tuple[str, ...]
    rejected_ids: tuple[str, ...]
    proof_refs: tuple[str, ...]
    explanation: Mapping[str, Any]
    external_effects: int = 0
    authority_created: bool = False

    def validate(self) -> "DecisionReceipt":
        safe_id(self.decision_id, "decision_id")
        if self.external_effects != 0 or self.authority_created:
            raise CivitasError("decision receipt must remain effect-free and non-authorizing")
        if self.disposition != DecisionDisposition.HOLD and not self.proof_refs:
            raise ValueError("selected decision requires proof references")
        return self

    @property
    def receipt_sha256(self) -> str:
        self.validate()
        return digest(asdict(self))


__all__ = [
    "SCHEMA", "VERSION", "AUTHORITY_CEILING", "EXTERNAL_EFFECTS",
    "CivitasError", "ProofLevel", "PROOF_RANK", "MaturityStage",
    "MATURITY_RANK", "AuthorityClass", "AUTHORITY_RANK",
    "DecisionDisposition", "VoteState", "ProofRef", "ObjectiveVector",
    "ResourceBudget", "ResourceDemand", "FitnessVector",
    "CapabilityDescriptor", "AssuranceVote", "MaturityEvidence",
    "DecisionReceipt", "digest", "safe_id", "parse_time",
    "contains_secret_shape", "proof_at_least", "maturity_at_most",
    "authority_at_most",
]
