"""Dependency-free execution budgets, routing, and circuit protection."""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetLimit:
    model_requests: int = 8
    tokens: int = 100_000
    tool_calls: int = 32
    retries: int = 3
    estimated_cost_microunits: int = 0


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: str
    model_requests: int
    tokens: int
    tool_calls: int
    retries: int
    estimated_cost_microunits: int


class BudgetLedger:
    """Atomically reserves bounded work so concurrent workers cannot overcommit."""

    _FIELDS = (
        "model_requests",
        "tokens",
        "tool_calls",
        "retries",
        "estimated_cost_microunits",
    )

    def __init__(self, limit: BudgetLimit) -> None:
        self.limit = limit
        self._used = {field: 0 for field in self._FIELDS}
        self._active: dict[str, BudgetReservation] = {}
        self._lock = threading.Lock()

    def reserve(self, **values: int) -> BudgetReservation:
        normalized = {field: int(values.get(field, 0)) for field in self._FIELDS}
        if any(value < 0 for value in normalized.values()):
            raise ValueError("Budget reservations cannot be negative")
        with self._lock:
            for field, value in normalized.items():
                if self._used[field] + value > getattr(self.limit, field):
                    raise BudgetExceeded(field)
            reservation = BudgetReservation(secrets.token_hex(12), **normalized)
            for field, value in normalized.items():
                self._used[field] += value
            self._active[reservation.reservation_id] = reservation
            return reservation

    def release(self, reservation_id: str) -> None:
        with self._lock:
            reservation = self._active.pop(reservation_id)
            for field in self._FIELDS:
                self._used[field] -= getattr(reservation, field)

    def commit(self, reservation_id: str) -> None:
        with self._lock:
            if reservation_id not in self._active:
                raise ValueError("Unknown budget reservation")
            self._active.pop(reservation_id)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._used)


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1 or recovery_seconds <= 0:
            raise ValueError("Invalid circuit-breaker policy")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.clock = clock
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        if self.opened_at is None:
            return CircuitState.CLOSED
        if self.clock() - self.opened_at >= self.recovery_seconds:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def allow(self) -> bool:
        return self.state is not CircuitState.OPEN

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self, *, retryable: bool) -> None:
        if not retryable:
            return
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = self.clock()


class ExecutionRoute(StrEnum):
    DIRECT_FUNCTION = "DIRECT_FUNCTION"
    SINGLE_AGENT = "SINGLE_AGENT"
    BOUNDED_SPECIALISTS = "BOUNDED_SPECIALISTS"


def select_execution_route(
    *, deterministic: bool, specialist_domains: int, security_isolation_required: bool
) -> ExecutionRoute:
    if deterministic and not security_isolation_required:
        return ExecutionRoute.DIRECT_FUNCTION
    if specialist_domains >= 2 or security_isolation_required:
        return ExecutionRoute.BOUNDED_SPECIALISTS
    return ExecutionRoute.SINGLE_AGENT
