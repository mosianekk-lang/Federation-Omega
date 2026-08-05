from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SignalKind = Literal[
    "STATE_OBSERVATION",
    "READBACK_MISMATCH",
    "CLAIM_EXCEEDS_PROOF",
    "EXTERNAL_EFFECT_REQUEST",
    "HUMAN_GATE_REQUIRED",
    "ROUTE_FAILURE",
    "CONTRADICTION",
    "STALE_MEMORY",
]
ControlStatus = Literal["HOMEOSTATIC", "DRIFT", "UNMEASURED"]
AuthorityClass = Literal["MACHINE_SAFE", "HUMAN_AUTHORITY_REQUIRED", "HUMAN_ONLY_GATE"]
DecisionState = Literal["READY", "HELD", "BLOCKED", "COMPLETED_SIMULATED"]
TerminalEvent = Literal["SUCCESS", "FAILURE", "CONSTRAINT"]


@dataclass(frozen=True)
class Signal:
    signal_id: str
    observed_at: str
    kind: SignalKind
    source: str
    payload: dict[str, Any]
    confidence: float = 1.0
    freshness: str = "CURRENT"
    privacy_tier: str = "A1_INTERNAL"

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ControlTarget:
    variable: str
    target: float
    tolerance: float = 0.0
    mandatory: bool = True

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise ValueError("tolerance cannot be negative")


@dataclass(frozen=True)
class StateObservation:
    variable: str
    target: float | None
    observed: float | None
    error: float | None
    tolerance: float | None
    status: ControlStatus
    confidence: float
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReflexRule:
    rule_id: str
    trigger_kind: SignalKind
    actions: tuple[str, ...]
    authority_class: AuthorityClass
    prohibited_actions: tuple[str, ...] = ()
    truth_boundary: str = ""


@dataclass(frozen=True)
class ActionDecision:
    decision_id: str
    signal_id: str
    action: str
    reason: str
    authority_class: AuthorityClass
    state: DecisionState
    requires_readback: bool = True
    external_effect: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CycleReceipt:
    contract: str
    cycle_id: str
    fixture_class: str
    started_at: str
    completed_at: str
    input_sha256: str
    output_sha256: str
    previous_receipt_hash: str | None
    receipt_hash: str
    terminal_event: TerminalEvent
    cycle_state: str
    mission_delta_before: int
    mission_delta_after: int
    closure_rate: float
    signals: tuple[dict[str, Any], ...]
    state_vector: tuple[dict[str, Any], ...]
    decisions: tuple[dict[str, Any], ...]
    checks: dict[str, bool]
    metrics: dict[str, int | float]
    open_constraints: tuple[str, ...]
    truth_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
