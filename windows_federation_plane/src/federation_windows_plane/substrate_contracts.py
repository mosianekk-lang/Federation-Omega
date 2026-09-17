from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Mapping


class ExecutorKind(str, Enum):
    WINDOWS_HOST = "WINDOWS_HOST"
    WINDOWS_HYPERV = "WINDOWS_HYPERV"
    WASM_SANDBOX = "WASM_SANDBOX"
    CONTAINER_SANDBOX = "CONTAINER_SANDBOX"
    GOOGLE_APPS_SCRIPT = "GOOGLE_APPS_SCRIPT"
    GOOGLE_CLOUD = "GOOGLE_CLOUD"
    GOOGLE_AI_STUDIO = "GOOGLE_AI_STUDIO"
    MODEL_PROVIDER = "MODEL_PROVIDER"
    REMOTE_EDGE = "REMOTE_EDGE"


class ProofMaturity(str, Enum):
    DISCOVERED = "DISCOVERED"
    AUTHENTICATED = "AUTHENTICATED"
    SOURCE_BOUND = "SOURCE_BOUND"
    EXECUTION_PROVEN = "EXECUTION_PROVEN"
    READBACK_PROVEN = "READBACK_PROVEN"
    PRODUCTION_ELIGIBLE = "PRODUCTION_ELIGIBLE"


@dataclass(frozen=True)
class ResourceVector:
    cpu: float = 0.0
    memory_gb: float = 0.0
    gpu: float = 0.0
    io: float = 0.0
    network: float = 0.0

    def fits(self, need: "ResourceVector") -> bool:
        return (
            self.cpu >= need.cpu
            and self.memory_gb >= need.memory_gb
            and self.gpu >= need.gpu
            and self.io >= need.io
            and self.network >= need.network
        )


@dataclass(frozen=True)
class CommercialProfile:
    """Normalized 0..1 commercial characteristics; higher is better except cost."""

    unit_cost: float = 0.5
    deployability: float = 0.5
    maintainability: float = 0.5
    scalability: float = 0.5
    interoperability: float = 0.5
    observability: float = 0.5
    supportability: float = 0.5
    differentiation: float = 0.5

    def value_score(self) -> float:
        strengths = (
            self.deployability
            + self.maintainability
            + self.scalability
            + self.interoperability
            + self.observability
            + self.supportability
            + self.differentiation
        ) / 7.0
        return max(0.0, min(1.0, strengths - (0.35 * self.unit_cost)))


@dataclass(frozen=True)
class ExecutorPassport:
    executor_id: str
    kind: ExecutorKind
    capabilities: FrozenSet[str]
    capacity: ResourceVector
    isolation: float
    locality: float
    resilience: float
    energy_efficiency: float
    startup_ms: float
    variable_cost: float = 0.0
    privacy_fit: float = 0.5
    residency_fit: float = 0.5
    accelerator_score: float = 0.0
    proof_maturity: ProofMaturity = ProofMaturity.DISCOVERED
    readback_mechanisms: FrozenSet[str] = field(default_factory=frozenset)
    commercial: CommercialProfile = field(default_factory=CommercialProfile)
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkloadSpec:
    workload_id: str
    required_capabilities: FrozenSet[str]
    resources: ResourceVector
    min_isolation: float = 0.0
    min_privacy_fit: float = 0.0
    min_residency_fit: float = 0.0
    latency_sensitivity: float = 0.5
    resilience_need: float = 0.5
    accelerator_affinity: float = 0.0
    commercial_priority: float = 0.5
    deterministic: bool = True
    allowed_executor_kinds: FrozenSet[ExecutorKind] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RoutingPolicy:
    latency_weight: float = 1.35
    failure_weight: float = 2.40
    pressure_weight: float = 1.10
    locality_weight: float = 0.70
    energy_weight: float = 0.35
    accelerator_weight: float = 0.75
    cost_weight: float = 0.85
    privacy_weight: float = 1.20
    commercial_weight: float = 1.00
    uncertainty_weight: float = 0.85
    spread_weight: float = 0.30
    exploration: float = 0.04

    def normalized(self) -> "RoutingPolicy":
        names = (
            "latency_weight",
            "failure_weight",
            "pressure_weight",
            "locality_weight",
            "energy_weight",
            "accelerator_weight",
            "cost_weight",
            "privacy_weight",
            "commercial_weight",
            "uncertainty_weight",
            "spread_weight",
        )
        vals = [max(0.01, float(getattr(self, n))) for n in names]
        scale = 11.0 / max(1e-9, sum(vals))
        payload = {n: v * scale for n, v in zip(names, vals)}
        payload["exploration"] = max(0.0, min(0.20, float(self.exploration)))
        return RoutingPolicy(**payload)
