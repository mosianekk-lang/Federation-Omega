"""Pure coalescing, rate-limit, and circuit-breaker policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .contracts import parse_utc
from .errors import ContractError
from .scoring import CapabilityCandidate, coalesce_candidates


@dataclass(frozen=True, slots=True)
class FlowPolicy:
    maximum_candidates: int = 16
    minimum_interval_seconds: int = 5
    failure_threshold: int = 3
    circuit_open_seconds: int = 60

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("maximum_candidates", 1, 64),
            ("minimum_interval_seconds", 0, 300),
            ("failure_threshold", 1, 10),
            ("circuit_open_seconds", 1, 3600),
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                raise ContractError(f"INVALID_FLOW_POLICY:{name}")


@dataclass(frozen=True, slots=True)
class FlowState:
    last_input_at: str | None = None
    consecutive_failures: int = 0
    circuit_open_until: str | None = None

    def __post_init__(self) -> None:
        if self.last_input_at is not None:
            parse_utc(self.last_input_at, field="last_input_at")
        if self.circuit_open_until is not None:
            parse_utc(self.circuit_open_until, field="circuit_open_until")
        if isinstance(self.consecutive_failures, bool) or not isinstance(self.consecutive_failures, int) or self.consecutive_failures < 0:
            raise ContractError("INVALID_FAILURE_COUNT")


@dataclass(frozen=True, slots=True)
class FlowDecision:
    candidates: tuple[CapabilityCandidate, ...]
    next_state: FlowState
    suppressed_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, (tuple, list)):
            raise ContractError("FLOW_CANDIDATES_SEQUENCE_REQUIRED")
        object.__setattr__(self, "candidates", tuple(self.candidates))


def apply_flow_policy(
    *,
    candidates: tuple[CapabilityCandidate, ...],
    now: str,
    policy: FlowPolicy,
    state: FlowState,
) -> FlowDecision:
    current = parse_utc(now, field="now")
    if state.circuit_open_until is not None and current < parse_utc(state.circuit_open_until, field="circuit_open_until"):
        return FlowDecision((), state, "CIRCUIT_OPEN")
    if state.last_input_at is not None:
        elapsed = (current - parse_utc(state.last_input_at, field="last_input_at")).total_seconds()
        if elapsed < policy.minimum_interval_seconds:
            return FlowDecision((), state, "RATE_LIMITED")
    coalesced = coalesce_candidates(candidates)[: policy.maximum_candidates]
    return FlowDecision(
        candidates=coalesced,
        next_state=FlowState(last_input_at=now, consecutive_failures=0, circuit_open_until=None),
        suppressed_reason="NONE",
    )


def record_flow_failure(*, now: str, policy: FlowPolicy, state: FlowState) -> FlowState:
    current = parse_utc(now, field="now")
    failures = state.consecutive_failures + 1
    open_until = None
    if failures >= policy.failure_threshold:
        open_until = (current + timedelta(seconds=policy.circuit_open_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return FlowState(
        last_input_at=state.last_input_at,
        consecutive_failures=failures,
        circuit_open_until=open_until,
    )
