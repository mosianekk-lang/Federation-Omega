from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .federation_evolution_program import (
    AUTHORITY_CEILING,
    EvolutionStage,
    StageEvidence,
    SYSTEM_PROFILES,
)


class SemanticState(str, Enum):
    UNKNOWN = "UNKNOWN"
    DECLARED_CONTRACT = "DECLARED_CONTRACT"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    RUNTIME_SEMANTIC_VERIFIED = "RUNTIME_SEMANTIC_VERIFIED"
    PROVIDER_SEMANTIC_VERIFIED = "PROVIDER_SEMANTIC_VERIFIED"


class ReadbackState(str, Enum):
    NONE = "NONE"
    SOURCE_READBACK = "SOURCE_READBACK"
    RUNTIME_READBACK = "RUNTIME_READBACK"
    PROVIDER_READBACK = "PROVIDER_READBACK"


class RuntimeState(str, Enum):
    UNKNOWN = "UNKNOWN"
    SOURCE_ONLY = "SOURCE_ONLY"
    RUNTIME_PARTIAL = "RUNTIME_PARTIAL"
    ADAPTER_REQUIRED = "ADAPTER_REQUIRED"
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"


class TwinState(str, Enum):
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    SOURCE_VERIFIED_RUNTIME_UNVERIFIED = "SOURCE_VERIFIED_RUNTIME_UNVERIFIED"
    CANONICAL_VERIFIED_ADAPTER_REQUIRED = "CANONICAL_VERIFIED_ADAPTER_REQUIRED"
    SOURCE_AND_TESTS_VERIFIED_RUNTIME_UNBOUND = "SOURCE_AND_TESTS_VERIFIED_RUNTIME_UNBOUND"
    RUNTIME_PARTIAL = "RUNTIME_PARTIAL"
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
    PROVIDER_VERIFIED = "PROVIDER_VERIFIED"


@dataclass(frozen=True)
class CapabilityTwin:
    system_id: str
    source_ref: str
    observed_at: str
    source_exists: bool
    canonical_readback: bool
    authority_ceiling: str
    semantic_state: SemanticState
    readback_state: ReadbackState
    runtime_state: RuntimeState
    proof_ref: str
    ttl_seconds: int = 3600
    age_seconds: int = 0
    provider_readback_ref: str = ""
    notes: str = ""

    def validate(self) -> "CapabilityTwin":
        if self.system_id not in SYSTEM_PROFILES:
            raise ValueError(f"unregistered Federation system: {self.system_id}")
        if not self.source_ref.strip() or not self.observed_at.strip():
            raise ValueError("source_ref and observed_at are required")
        if self.authority_ceiling != AUTHORITY_CEILING:
            raise ValueError("capability twin cannot expand authority")
        if self.ttl_seconds <= 0 or self.age_seconds < 0:
            raise ValueError("invalid freshness values")
        if self.canonical_readback and not self.source_exists:
            raise ValueError("canonical readback cannot exist without source")
        if self.source_exists and not self.proof_ref.strip():
            raise ValueError("observed source requires proof_ref")
        if self.readback_state == ReadbackState.NONE and self.canonical_readback:
            raise ValueError("canonical_readback requires a readback state")
        if self.runtime_state == RuntimeState.RUNTIME_VERIFIED:
            if self.semantic_state not in {
                SemanticState.RUNTIME_SEMANTIC_VERIFIED,
                SemanticState.PROVIDER_SEMANTIC_VERIFIED,
            }:
                raise ValueError("runtime verification requires semantic runtime proof")
            if self.readback_state not in {ReadbackState.RUNTIME_READBACK, ReadbackState.PROVIDER_READBACK}:
                raise ValueError("runtime verification requires runtime/provider readback")
        if self.runtime_state == RuntimeState.PROVIDER_VERIFIED:
            if self.semantic_state != SemanticState.PROVIDER_SEMANTIC_VERIFIED:
                raise ValueError("provider verification requires provider semantic proof")
            if self.readback_state != ReadbackState.PROVIDER_READBACK:
                raise ValueError("provider verification requires provider readback state")
            if not self.provider_readback_ref.strip():
                raise ValueError("provider verification requires provider readback reference")
        if self.semantic_state == SemanticState.PROVIDER_SEMANTIC_VERIFIED and not self.provider_readback_ref.strip():
            raise ValueError("provider semantic state requires provider readback reference")
        return self

    @property
    def fresh(self) -> bool:
        return self.age_seconds <= self.ttl_seconds

    @property
    def twin_state(self) -> TwinState:
        self.validate()
        if not self.fresh:
            return TwinState.STALE
        if not self.source_exists or not self.canonical_readback:
            return TwinState.UNKNOWN
        if self.runtime_state == RuntimeState.PROVIDER_VERIFIED:
            return TwinState.PROVIDER_VERIFIED
        if self.runtime_state == RuntimeState.RUNTIME_VERIFIED:
            return TwinState.RUNTIME_VERIFIED
        if self.runtime_state == RuntimeState.RUNTIME_PARTIAL:
            return TwinState.RUNTIME_PARTIAL
        if self.runtime_state == RuntimeState.ADAPTER_REQUIRED:
            return TwinState.CANONICAL_VERIFIED_ADAPTER_REQUIRED
        if self.runtime_state == RuntimeState.SOURCE_ONLY:
            if self.semantic_state == SemanticState.DETERMINISTIC_TESTED:
                return TwinState.SOURCE_AND_TESTS_VERIFIED_RUNTIME_UNBOUND
            return TwinState.SOURCE_VERIFIED_RUNTIME_UNVERIFIED
        return TwinState.UNKNOWN

    @property
    def resolution_complete(self) -> bool:
        """EVO-02 measures truthful state resolution rather than forced liveness."""
        self.validate()
        return (
            self.fresh
            and self.source_exists
            and self.canonical_readback
            and self.semantic_state != SemanticState.UNKNOWN
            and self.readback_state != ReadbackState.NONE
            and self.runtime_state != RuntimeState.UNKNOWN
            and self.twin_state != TwinState.UNKNOWN
        )

    @property
    def confidence(self) -> float:
        self.validate()
        if not self.resolution_complete:
            return 0.0
        weights = {
            TwinState.SOURCE_VERIFIED_RUNTIME_UNVERIFIED: 0.45,
            TwinState.CANONICAL_VERIFIED_ADAPTER_REQUIRED: 0.50,
            TwinState.SOURCE_AND_TESTS_VERIFIED_RUNTIME_UNBOUND: 0.65,
            TwinState.RUNTIME_PARTIAL: 0.72,
            TwinState.RUNTIME_VERIFIED: 0.88,
            TwinState.PROVIDER_VERIFIED: 1.00,
        }
        return weights.get(self.twin_state, 0.0)

    def to_stage_evidence(self) -> StageEvidence:
        return StageEvidence(
            stage=EvolutionStage.CAPABILITY_DIGITAL_TWIN,
            passed=self.resolution_complete,
            proof_ref=self.proof_ref if self.resolution_complete else "",
            score=self.confidence,
            regression_passed=False,
            rollback_available=False,
            provider_readback=self.twin_state == TwinState.PROVIDER_VERIFIED,
            external_effect=False,
        ).validate()


@dataclass(frozen=True)
class FederationTwinRollup:
    twins: tuple[CapabilityTwin, ...]

    def validate(self, *, require_all_profiles: bool = True) -> "FederationTwinRollup":
        seen: set[str] = set()
        for twin in self.twins:
            twin.validate()
            if twin.system_id in seen:
                raise ValueError(f"duplicate capability twin: {twin.system_id}")
            seen.add(twin.system_id)
        if require_all_profiles:
            missing = sorted(set(SYSTEM_PROFILES) - seen)
            extra = sorted(seen - set(SYSTEM_PROFILES))
            if missing or extra:
                raise ValueError(f"capability twin coverage mismatch missing={missing} extra={extra}")
        return self

    @property
    def resolved_systems(self) -> tuple[str, ...]:
        self.validate(require_all_profiles=False)
        return tuple(sorted(t.system_id for t in self.twins if t.resolution_complete))

    @property
    def unresolved_systems(self) -> tuple[str, ...]:
        self.validate(require_all_profiles=False)
        return tuple(sorted(t.system_id for t in self.twins if not t.resolution_complete))

    def state_counts(self) -> Mapping[str, int]:
        self.validate(require_all_profiles=False)
        counts: dict[str, int] = {}
        for twin in self.twins:
            state = twin.twin_state.value
            counts[state] = counts.get(state, 0) + 1
        return dict(sorted(counts.items()))


__all__ = [
    "CapabilityTwin",
    "FederationTwinRollup",
    "ReadbackState",
    "RuntimeState",
    "SemanticState",
    "TwinState",
]
