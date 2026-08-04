from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Callable


class AttemptStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


class FailureClass(StrEnum):
    AUTHORITY = "AUTHORITY"
    CAPACITY = "CAPACITY"
    CONNECTIVITY = "CONNECTIVITY"
    PROVIDER_LIMIT = "PROVIDER_LIMIT"
    TIMEOUT = "TIMEOUT"
    INTEGRITY = "INTEGRITY"
    INVALID_INPUT = "INVALID_INPUT"
    UNKNOWN = "UNKNOWN"


class ProofLevel(StrEnum):
    DECLARED = "DECLARED"
    LOCALLY_TESTED = "LOCALLY_TESTED"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    INDEPENDENT_READBACK = "INDEPENDENT_READBACK"
    COMPLETE_VERIFIED = "COMPLETE_VERIFIED"


@dataclass(slots=True)
class CompletionGate:
    gate_id: str
    description: str
    mandatory: bool = True
    passed: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvidenceJob:
    job_id: str
    operation: str
    source: dict[str, Any]
    expected_outputs: list[dict[str, Any]]
    gates: list[CompletionGate]
    idempotency_key: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LaneResult:
    status: AttemptStatus
    details: dict[str, Any] = field(default_factory=dict)
    failure_class: FailureClass | None = None
    retryable: bool = False
    changed_condition_required: bool = True


LaneExecutor = Callable[[EvidenceJob], LaneResult]


@dataclass(slots=True)
class ExecutionLane:
    lane_id: str
    executor: LaneExecutor
    authority: float = 0.5
    capacity: float = 0.5
    reliability: float = 0.5
    proof_quality: float = 0.5
    cost: float = 0.0
    enabled: bool = True
    tags: set[str] = field(default_factory=set)

    def score(self) -> float:
        return (
            self.authority * 0.25
            + self.capacity * 0.20
            + self.reliability * 0.25
            + self.proof_quality * 0.30
            - self.cost * 0.10
        )


@dataclass(slots=True)
class ResolvePolicy:
    max_attempts: int = 8
    circuit_breaker_threshold: int = 1
    require_independent_readback: bool = True
    allow_partial_receipt: bool = True
    repeat_failed_lane_only_after_condition_change: bool = True
