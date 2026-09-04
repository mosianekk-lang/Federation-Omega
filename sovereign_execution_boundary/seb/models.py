from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any


class MissionState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRIED = "RETRIED"
    CANCELLED = "CANCELLED"
    DEAD_LETTER = "DEAD_LETTER"
    ROLLED_BACK = "ROLLED_BACK"
    QUARANTINED = "QUARANTINED"
    BLOCKED_INCOMPLETE = "BLOCKED_INCOMPLETE"


class FailureClass(StrEnum):
    TRANSIENT = "TRANSIENT"
    PROVIDER_OUTAGE = "PROVIDER_OUTAGE"
    MODEL_WEAKNESS = "MODEL_WEAKNESS"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    POLICY_REFUSAL = "POLICY_REFUSAL"
    MISSING_AUTHORITY = "MISSING_AUTHORITY"
    SEMANTIC_FAILURE = "SEMANTIC_FAILURE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    PRIVACY_VIOLATION = "PRIVACY_VIOLATION"
    DUPLICATE_EFFECT = "DUPLICATE_EFFECT"


@dataclass(frozen=True)
class Budget:
    money_usd: float = 0.0
    max_tokens: int = 4_000
    time_seconds: int = 300

    def validate(self) -> None:
        if self.money_usd < 0 or self.max_tokens <= 0 or self.time_seconds <= 0:
            raise ValueError("invalid budget")


@dataclass(frozen=True)
class MissionIR:
    mission_id: str
    objective: str
    requirements: tuple[str, ...]
    acceptance_tests: tuple[str, ...]
    authority_class: str = "A0"
    data_class: str = "private"
    prohibited_effects: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    budget: Budget = field(default_factory=Budget)
    version: int = 1

    def validate(self) -> None:
        if not self.mission_id.strip() or not self.objective.strip():
            raise ValueError("mission_id and objective are required")
        if self.authority_class not in {f"A{i}" for i in range(6)}:
            raise ValueError("unknown authority class")
        if self.data_class not in {"public", "private", "legal", "secret"}:
            raise ValueError("unknown data class")
        if self.version < 1:
            raise ValueError("version must be positive")
        self.budget.validate()

    @property
    def fingerprint(self) -> str:
        body = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class CompletionEvidence:
    """Evidence for the conditions that must all hold before COMPLETE is lawful."""
    objective_fingerprint: str
    satisfied_requirements: tuple[str, ...] = ()
    passed_acceptance_tests: tuple[str, ...] = ()
    native_effect_readbacks: tuple[str, ...] = ()
    preserved_invariants: tuple[str, ...] = ()
    unresolved_contradictions: tuple[str, ...] = ()
    rollback_viable: bool = False
    within_budget: bool = False


@dataclass(frozen=True)
class CompletionDecision:
    complete: bool
    defects: tuple[str, ...]
    proof_hash: str


@dataclass(frozen=True)
class ProviderRequest:
    mission_id: str
    request_id: str
    prompt: str
    schema: dict[str, Any]
    model: str
    max_tokens: int
    data_class: str


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model: str
    content: dict[str, Any]
    tokens: int
    latency_ms: int
    refusal: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    decision_id: str


@dataclass(frozen=True)
class ExecutionResult:
    mission_id: str
    state: MissionState
    output: dict[str, Any] | None
    provider: str | None
    attempts: int
    proof: tuple[str, ...]
    failure_class: FailureClass | None = None
    message: str = ""
