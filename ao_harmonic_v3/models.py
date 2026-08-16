from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TruthState(str, Enum):
    VERIFIED = "VERIFIED"
    USER_SUPPLIED = "USER_SUPPLIED"
    INFERENCE = "INFERENCE"
    UNVERIFIED = "UNVERIFIED"
    DISPUTED = "DISPUTED"
    CONTRADICTED = "CONTRADICTED"
    MISSING_PRIMARY_RECORD = "MISSING_PRIMARY_RECORD"
    UNKNOWN = "UNKNOWN"


class NodeState(str, Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    FAILED = "FAILED"
    RETRYABLE = "RETRYABLE"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"


class RiskClass(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Maturity(str, Enum):
    DESIGN_ONLY = "DESIGN_ONLY"
    SOURCE_IMPLEMENTED = "SOURCE_IMPLEMENTED"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    ADVERSARIALLY_TESTED = "ADVERSARIALLY_TESTED"
    SHADOW_VALIDATED = "SHADOW_VALIDATED"
    CANARY_VALIDATED = "CANARY_VALIDATED"
    WORKFLOW_VERIFIED = "WORKFLOW_VERIFIED"
    OPERATIONAL_VERIFIED = "OPERATIONAL_VERIFIED"
    CANONICAL = "CANONICAL"


@dataclass(frozen=True)
class FederationEvent:
    event_id: str
    event_type: str
    source: str
    workstream: str
    idempotency_key: str
    timestamp: str
    actor: str | None = None
    target: str | None = None
    proof_class: str | None = None
    privacy_class: str | None = None
    authority_class: str | None = None
    affected_state_keys: tuple[str, ...] = ()
    affected_mission_nodes: tuple[str, ...] = ()
    correlation_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass
class MissionNode:
    node_id: str
    objective: str
    dependencies: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    capability_required: list[str] = field(default_factory=list)
    authority_required: str | None = None
    expected_information_gain: float = 0.0
    expected_value: float = 0.0
    expected_latency: float = 1.0
    risk: float = 0.0
    status: NodeState = NodeState.READY
    assigned_system: str | None = None
    assigned_resource: str | None = None
    proof_refs: list[str] = field(default_factory=list)
    next_action: str | None = None


@dataclass
class Mission:
    mission_id: str
    objective: str
    desired_outcome: str
    risk_class: RiskClass
    success_definition: str = ""
    privacy_class: str = "P1"
    authority_ceiling: str = "A1_INTERNAL"
    status: str = "READY"
    nodes: dict[str, MissionNode] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceOffer:
    resource_id: str
    provider: str
    capability: str
    semantic_scope: str
    authority_ceiling: str
    maturity: Maturity
    privacy_class: str = "P1"
    relevance: float = 1.0
    semantic_fit: float = 1.0
    freshness: float = 1.0
    reliability: float = 1.0
    proof_strength: float = 1.0
    executability: float = 1.0
    information_gain: float = 1.0
    latency: float = 1.0
    owner_burden: float = 0.0
    privacy_cost: float = 0.0
    duplication_cost: float = 0.0
    failure_risk: float = 0.0
    rollback_available: bool = False


@dataclass
class ProofNode:
    proof_node_id: str
    node_type: str
    statement: str
    verification_status: TruthState
    confidence: float = 0.0
    source_refs: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    supports: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PerformanceVector:
    quality: float = 0.0
    reliability: float = 0.0
    proof: float = 0.0
    speed: float = 0.0
    owner_time_recovered: float = 0.0
    privacy_gain: float = 0.0
    recovery_gain: float = 0.0
    simplicity_gain: float = 0.0
    false_blocks: float = 0.0
    error_cost: float = 0.0
    latency_cost: float = 0.0
    owner_burden: float = 0.0
    privacy_risk: float = 0.0
    complexity: float = 0.0
    maintenance_cost: float = 0.0
    regression_risk: float = 0.0


@dataclass(frozen=True)
class ArchitectureComponent:
    component_id: str
    unique_function: bool
    usage: float
    overlap: float
    maintenance_cost: float
    owner_value: float
