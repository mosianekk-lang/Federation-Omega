from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from .models import Maturity, TruthState


class ForestIntegrityError(ValueError):
    pass


class FreshnessState(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    NON_EXPIRING = "NON_EXPIRING"
    UNKNOWN = "UNKNOWN"


class ConfidenceBand(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return sha256(_stable_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceAtom:
    evidence_id: str
    statement: str
    truth_state: TruthState
    source_refs: tuple[str, ...] = ()
    observed_at: str | None = None
    verified_at: str | None = None
    ttl_seconds: int | None = None
    confidence_band: ConfidenceBand = ConfidenceBand.LOW
    direct: bool = False
    disputed: bool = False
    supports: tuple[str, ...] = ()
    contradicted_by: tuple[str, ...] = ()
    scope: str = "GENERAL"
    privacy_class: str = "P1"
    synthetic: bool = False
    provenance_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ForestIntegrityError("EVIDENCE_ID_REQUIRED")
        if not self.statement.strip():
            raise ForestIntegrityError("EVIDENCE_STATEMENT_REQUIRED")
        if self.ttl_seconds is not None and self.ttl_seconds <= 0:
            raise ForestIntegrityError("EVIDENCE_TTL_MUST_BE_POSITIVE")
        if self.truth_state is TruthState.VERIFIED:
            if not self.source_refs:
                raise ForestIntegrityError("VERIFIED_EVIDENCE_REQUIRES_SOURCE_REF")
            if _parse_time(self.verified_at) is None:
                raise ForestIntegrityError("VERIFIED_EVIDENCE_REQUIRES_VERIFIED_AT")
        canonical = {
            "evidence_id": self.evidence_id,
            "statement": self.statement,
            "truth_state": self.truth_state.value,
            "source_refs": list(self.source_refs),
            "observed_at": self.observed_at,
            "verified_at": self.verified_at,
            "ttl_seconds": self.ttl_seconds,
            "confidence_band": self.confidence_band.value,
            "direct": self.direct,
            "disputed": self.disputed,
            "supports": list(self.supports),
            "contradicted_by": list(self.contradicted_by),
            "scope": self.scope,
            "privacy_class": self.privacy_class,
            "synthetic": self.synthetic,
        }
        computed = _hash_payload(canonical)
        if self.provenance_sha256 and self.provenance_sha256 != computed:
            raise ForestIntegrityError("EVIDENCE_PROVENANCE_HASH_MISMATCH")
        if not self.provenance_sha256:
            object.__setattr__(self, "provenance_sha256", computed)

    def freshness(self, *, as_of: str | None = None) -> FreshnessState:
        if self.ttl_seconds is None:
            return FreshnessState.NON_EXPIRING
        verified = _parse_time(self.verified_at)
        if verified is None:
            return FreshnessState.UNKNOWN
        now = _parse_time(as_of) if as_of else datetime.now(timezone.utc)
        assert now is not None
        age = (now - verified).total_seconds()
        return FreshnessState.CURRENT if age <= self.ttl_seconds else FreshnessState.STALE

    def consequentially_usable(self, *, as_of: str | None = None) -> bool:
        freshness = self.freshness(as_of=as_of)
        return bool(
            self.truth_state is TruthState.VERIFIED
            and self.source_refs
            and freshness in {FreshnessState.CURRENT, FreshnessState.NON_EXPIRING}
            and not self.disputed
            and not self.contradicted_by
            and not self.synthetic
        )


@dataclass(frozen=True, slots=True)
class ObjectiveGenome:
    objective_id: str
    objective: str
    desired_outcome: str
    success_conditions: tuple[str, ...]
    acceptable_substitutes: tuple[str, ...] = ()
    non_negotiables: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    failure_conditions: tuple[str, ...] = ()
    stop_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.objective_id.strip():
            raise ForestIntegrityError("OBJECTIVE_ID_REQUIRED")
        if not self.objective.strip():
            raise ForestIntegrityError("OBJECTIVE_REQUIRED")
        if not self.desired_outcome.strip():
            raise ForestIntegrityError("DESIRED_OUTCOME_REQUIRED")
        if not self.success_conditions:
            raise ForestIntegrityError("SUCCESS_CONDITION_REQUIRED")


@dataclass(frozen=True, slots=True)
class PathCandidate:
    path_id: str
    available: bool
    authorised: bool
    safe: bool
    deadline_viable: bool
    privacy_acceptable: bool
    cost_acceptable: bool
    dependencies_ready: bool
    evidence_sufficient: bool
    rollback_available: bool
    strategic_value: float = 0.0
    proof_strength: float = 0.0
    reversibility: float = 0.0
    information_gain: float = 0.0
    owner_burden: float = 0.0
    maintenance_cost: float = 0.0

    def eligible(self, *, rollback_required: bool = False) -> bool:
        checks = (
            self.available,
            self.authorised,
            self.safe,
            self.deadline_viable,
            self.privacy_acceptable,
            self.cost_acceptable,
            self.dependencies_ready,
            self.evidence_sufficient,
        )
        return all(checks) and (self.rollback_available or not rollback_required)

    def score(self) -> float:
        return (
            self.strategic_value
            + self.proof_strength
            + self.reversibility
            + self.information_gain
            - self.owner_burden
            - self.maintenance_cost
        )


def rank_admissible_paths(
    paths: Iterable[PathCandidate], *, rollback_required: bool = False
) -> tuple[PathCandidate, ...]:
    eligible = [path for path in paths if path.eligible(rollback_required=rollback_required)]
    return tuple(sorted(eligible, key=lambda path: (-path.score(), path.path_id)))


@dataclass(frozen=True, slots=True)
class DecisionContract:
    decision_id: str
    objective: ObjectiveGenome
    evidence_refs: tuple[str, ...]
    alternatives: tuple[str, ...]
    selected_path: PathCandidate
    uncertainty_band: ConfidenceBand
    irreversibility: float
    owner_authority_required: bool
    owner_approved: bool = False
    valid_until: str | None = None
    stop_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.decision_id.strip():
            raise ForestIntegrityError("DECISION_ID_REQUIRED")
        if not 0.0 <= self.irreversibility <= 1.0:
            raise ForestIntegrityError("IRREVERSIBILITY_RANGE_REQUIRED")
        if self.irreversibility >= 0.7 and not self.owner_authority_required:
            raise ForestIntegrityError("HIGH_IRREVERSIBILITY_REQUIRES_OWNER_AUTHORITY")

    def release_allowed(self, *, as_of: str | None = None) -> bool:
        if not self.selected_path.eligible(rollback_required=self.irreversibility >= 0.7):
            return False
        if self.owner_authority_required and not self.owner_approved:
            return False
        expiry = _parse_time(self.valid_until)
        now = _parse_time(as_of) if as_of else datetime.now(timezone.utc)
        if expiry is not None and now is not None and now > expiry:
            return False
        return True


@dataclass(frozen=True, slots=True)
class EffectContract:
    effect_id: str
    target: str
    prior_state_sha256: str
    expected_delta: Mapping[str, Any]
    authority_ref: str
    rollback_ref: str
    success_predicate: str

    def __post_init__(self) -> None:
        for label, value in (
            ("effect_id", self.effect_id),
            ("target", self.target),
            ("prior_state_sha256", self.prior_state_sha256),
            ("authority_ref", self.authority_ref),
            ("rollback_ref", self.rollback_ref),
            ("success_predicate", self.success_predicate),
        ):
            if not str(value).strip():
                raise ForestIntegrityError(f"{label.upper()}_REQUIRED")
        if not self.expected_delta:
            raise ForestIntegrityError("EXPECTED_DELTA_REQUIRED")


@dataclass(frozen=True, slots=True)
class ReadbackReceipt:
    effect_id: str
    target: str
    prior_state_sha256: str
    after_state_sha256: str
    observed_delta: Mapping[str, Any]
    provider_ref: str
    readback_at: str
    semantic_success: bool
    receipt_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.provider_ref.strip():
            raise ForestIntegrityError("READBACK_PROVIDER_REF_REQUIRED")
        if _parse_time(self.readback_at) is None:
            raise ForestIntegrityError("READBACK_TIMESTAMP_REQUIRED")
        canonical = {
            "effect_id": self.effect_id,
            "target": self.target,
            "prior_state_sha256": self.prior_state_sha256,
            "after_state_sha256": self.after_state_sha256,
            "observed_delta": dict(self.observed_delta),
            "provider_ref": self.provider_ref,
            "readback_at": self.readback_at,
            "semantic_success": self.semantic_success,
        }
        computed = _hash_payload(canonical)
        if self.receipt_sha256 and self.receipt_sha256 != computed:
            raise ForestIntegrityError("READBACK_RECEIPT_HASH_MISMATCH")
        if not self.receipt_sha256:
            object.__setattr__(self, "receipt_sha256", computed)


def effect_proved(contract: EffectContract, receipt: ReadbackReceipt) -> bool:
    if not receipt.semantic_success:
        return False
    if contract.effect_id != receipt.effect_id or contract.target != receipt.target:
        return False
    if contract.prior_state_sha256 != receipt.prior_state_sha256:
        return False
    if not receipt.after_state_sha256 or receipt.after_state_sha256 == receipt.prior_state_sha256:
        return False
    return all(receipt.observed_delta.get(key) == value for key, value in contract.expected_delta.items())


@dataclass(frozen=True, slots=True)
class CapabilityTruth:
    capability_id: str
    source_present: bool
    connected: bool
    authorised: bool
    provider_verified: bool
    semantic_success: bool
    fresh: bool
    maturity: Maturity
    fallback_available: bool = False
    cost_class: str = "UNKNOWN"

    def executable(self, *, minimum_maturity: Maturity = Maturity.WORKFLOW_VERIFIED) -> bool:
        order = list(Maturity)
        return bool(
            self.connected
            and self.authorised
            and self.provider_verified
            and self.semantic_success
            and self.fresh
            and order.index(self.maturity) >= order.index(minimum_maturity)
        )


@dataclass(frozen=True, slots=True)
class ComplexityBudget:
    component_id: str
    proposed_units: float
    replaced_units: float
    measurable_capability_gain: bool
    owner_burden_delta: float
    maintenance_delta: float
    unique_failure_domain: bool = False

    def admitted(self) -> bool:
        if self.proposed_units < 0 or self.replaced_units < 0:
            raise ForestIntegrityError("COMPLEXITY_UNITS_NON_NEGATIVE_REQUIRED")
        if not self.measurable_capability_gain:
            return False
        net_units = self.proposed_units - self.replaced_units
        if net_units <= 0:
            return True
        return bool(
            self.unique_failure_domain
            and self.owner_burden_delta <= 0
            and self.maintenance_delta <= 0
        )


@dataclass(frozen=True, slots=True)
class ForestFitnessObservation:
    observation_id: str
    evidence_refs: tuple[str, ...]
    outcome_success: bool
    strategic_surprises: int
    false_claims: int
    irreversible_errors: int
    owner_minutes: float
    useful_outcome_latency_seconds: float
    synthetic: bool = False

    def eligible_for_empirical_learning(self) -> bool:
        return bool(
            self.observation_id.strip()
            and self.evidence_refs
            and not self.synthetic
            and self.strategic_surprises >= 0
            and self.false_claims >= 0
            and self.irreversible_errors >= 0
            and self.owner_minutes >= 0
            and self.useful_outcome_latency_seconds >= 0
        )


__all__ = [
    "CapabilityTruth",
    "ComplexityBudget",
    "ConfidenceBand",
    "DecisionContract",
    "EffectContract",
    "EvidenceAtom",
    "ForestFitnessObservation",
    "ForestIntegrityError",
    "FreshnessState",
    "ObjectiveGenome",
    "PathCandidate",
    "ReadbackReceipt",
    "effect_proved",
    "rank_admissible_paths",
]
