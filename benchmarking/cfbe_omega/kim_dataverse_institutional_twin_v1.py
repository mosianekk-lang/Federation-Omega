from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import MaturityState, OwnerBoundary


class CapabilityHealth(str, Enum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class CapabilityObservation:
    capability_id: str
    source_sha: str
    maturity: MaturityState
    health: CapabilityHealth
    proof_refs: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    authority_boundary: OwnerBoundary = OwnerBoundary.NONE
    owner_burden_minutes: float | None = None
    cost_units: float | None = None
    reliability: float | None = None
    observed_at: str = ""


@dataclass(frozen=True)
class CapabilityProjection:
    capability_id: str
    source_sha: str
    maturity: MaturityState
    health: CapabilityHealth
    proof_refs: tuple[str, ...]
    dependencies: tuple[str, ...]
    authority_boundary: OwnerBoundary
    owner_burden_minutes: float | None
    cost_units: float | None
    reliability: float | None
    observed_at: str


@dataclass(frozen=True)
class InstitutionalTwin:
    capabilities: tuple[CapabilityProjection, ...]
    unresolved_dependencies: tuple[tuple[str, str], ...]
    provider_verified_count: int
    operationally_observed_count: int
    value_proven_count: int
    stale_or_degraded_count: int
    authority_bound_count: int

    def digest(self) -> str:
        payload = {
            "capabilities": [
                {
                    **item.__dict__,
                    "maturity": item.maturity.value,
                    "health": item.health.value,
                    "authority_boundary": item.authority_boundary.value,
                }
                for item in self.capabilities
            ],
            "unresolved_dependencies": self.unresolved_dependencies,
            "provider_verified_count": self.provider_verified_count,
            "operationally_observed_count": self.operationally_observed_count,
            "value_proven_count": self.value_proven_count,
            "stale_or_degraded_count": self.stale_or_degraded_count,
            "authority_bound_count": self.authority_bound_count,
            "external_effect": False,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + sha256(encoded).hexdigest()


def _validate_observation(observation: CapabilityObservation) -> None:
    if not observation.capability_id.strip():
        raise ValueError("capability_id is required")
    if len(observation.source_sha) < 7:
        raise ValueError("source_sha is required")
    if observation.maturity in {
        MaturityState.PROVIDER_VERIFIED,
        MaturityState.OPERATIONALLY_OBSERVED,
        MaturityState.VALUE_PROVEN,
    } and not observation.proof_refs:
        raise ValueError("higher maturity requires proof_refs")
    if observation.reliability is not None and not 0.0 <= observation.reliability <= 1.0:
        raise ValueError("reliability must be within [0, 1]")
    if observation.owner_burden_minutes is not None and observation.owner_burden_minutes < 0:
        raise ValueError("owner_burden_minutes must be non-negative")
    if observation.cost_units is not None and observation.cost_units < 0:
        raise ValueError("cost_units must be non-negative")


def build_institutional_twin(observations: Sequence[CapabilityObservation]) -> InstitutionalTwin:
    ids = [item.capability_id for item in observations]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate capability observation")
    for observation in observations:
        _validate_observation(observation)

    known = set(ids)
    unresolved: list[tuple[str, str]] = []
    projections: list[CapabilityProjection] = []
    for observation in sorted(observations, key=lambda item: item.capability_id):
        for dependency in observation.dependencies:
            if dependency not in known:
                unresolved.append((observation.capability_id, dependency))
        projections.append(
            CapabilityProjection(
                capability_id=observation.capability_id,
                source_sha=observation.source_sha,
                maturity=observation.maturity,
                health=observation.health,
                proof_refs=tuple(sorted(set(observation.proof_refs))),
                dependencies=tuple(sorted(set(observation.dependencies))),
                authority_boundary=observation.authority_boundary,
                owner_burden_minutes=observation.owner_burden_minutes,
                cost_units=observation.cost_units,
                reliability=observation.reliability,
                observed_at=observation.observed_at,
            )
        )

    return InstitutionalTwin(
        capabilities=tuple(projections),
        unresolved_dependencies=tuple(sorted(unresolved)),
        provider_verified_count=sum(p.maturity == MaturityState.PROVIDER_VERIFIED for p in projections),
        operationally_observed_count=sum(p.maturity == MaturityState.OPERATIONALLY_OBSERVED for p in projections),
        value_proven_count=sum(p.maturity == MaturityState.VALUE_PROVEN for p in projections),
        stale_or_degraded_count=sum(p.health in {CapabilityHealth.STALE, CapabilityHealth.DEGRADED} for p in projections),
        authority_bound_count=sum(p.authority_boundary != OwnerBoundary.NONE for p in projections),
    )


def capability_reuse_candidates(
    twin: InstitutionalTwin,
    required_dependencies: Iterable[str],
    *,
    minimum_reliability: float = 0.0,
) -> tuple[str, ...]:
    required = set(required_dependencies)
    if not 0.0 <= minimum_reliability <= 1.0:
        raise ValueError("minimum_reliability must be within [0,1]")
    eligible = []
    for capability in twin.capabilities:
        if capability.health != CapabilityHealth.HEALTHY:
            continue
        if capability.maturity in {MaturityState.STALE, MaturityState.DEGRADED, MaturityState.RETIRED}:
            continue
        if capability.reliability is not None and capability.reliability < minimum_reliability:
            continue
        if required and not required.issubset(set(capability.dependencies) | {capability.capability_id}):
            continue
        eligible.append(capability.capability_id)
    return tuple(sorted(eligible))


def proof_state_counts(twin: InstitutionalTwin) -> Mapping[str, int]:
    counts = {state.value: 0 for state in MaturityState}
    for capability in twin.capabilities:
        counts[capability.maturity.value] += 1
    return counts
