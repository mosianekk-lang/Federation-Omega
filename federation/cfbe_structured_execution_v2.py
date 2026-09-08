"""CFBE Ω structured read execution + dynamic circuit primitives v2.

This module provides a bounded async executor for READ_ONLY / NO_EFFECT work and a
route circuit state machine. It never authorises mutation or provider effects.
Effectful work must remain behind the existing FUSE/N-OMEGA admission/fencing path.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any, Awaitable, Callable, Mapping, Sequence

SCHEMA = "CFBE-STRUCTURED-EXECUTION-V2"
VERSION = "2.0.0"


@dataclass(frozen=True, slots=True)
class AsyncReadTask:
    task_id: str
    surface: str
    run: Callable[[], Awaitable[Any]]
    timeout_seconds: float = 30.0
    idempotent: bool = True
    read_only: bool = True

    def validate(self) -> None:
        if not self.task_id.strip() or not self.surface.strip():
            raise ValueError("ASYNC_TASK_IDENTITY_REQUIRED")
        if self.timeout_seconds <= 0:
            raise ValueError("ASYNC_TASK_TIMEOUT_INVALID")
        if not self.read_only:
            raise ValueError("STRUCTURED_EXECUTOR_READ_ONLY_ONLY")
        if not self.idempotent:
            raise ValueError("STRUCTURED_EXECUTOR_IDEMPOTENT_ONLY")


@dataclass(frozen=True, slots=True)
class AsyncReadResult:
    task_id: str
    surface: str
    state: str
    latency_ms: int
    value: Any = None
    error_type: str = ""
    error_message: str = ""

    @property
    def success(self) -> bool:
        return self.state == "SUCCESS"


@dataclass(frozen=True, slots=True)
class StructuredExecutionReceipt:
    results: tuple[AsyncReadResult, ...]
    max_parallel_observed: int
    surface_peak: tuple[tuple[str, int], ...]


class StructuredReadExecutor:
    """TaskGroup-backed, deadline-bounded, per-surface-bulkheaded read executor."""

    def __init__(self, *, global_max_parallel: int = 8, surface_limits: Mapping[str, int] | None = None) -> None:
        if global_max_parallel < 1:
            raise ValueError("GLOBAL_PARALLEL_INVALID")
        self.global_max_parallel = global_max_parallel
        self.surface_limits = dict(surface_limits or {})
        if any(v < 1 for v in self.surface_limits.values()):
            raise ValueError("SURFACE_LIMIT_INVALID")

    async def execute(self, tasks: Sequence[AsyncReadTask]) -> StructuredExecutionReceipt:
        ids = [t.task_id for t in tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("DUPLICATE_TASK_ID")
        for task in tasks:
            task.validate()

        global_sem = asyncio.Semaphore(self.global_max_parallel)
        surface_sems = {
            surface: asyncio.Semaphore(limit)
            for surface, limit in self.surface_limits.items()
        }
        results: dict[str, AsyncReadResult] = {}
        active = 0
        peak = 0
        surface_active: dict[str, int] = {}
        surface_peak: dict[str, int] = {}
        counter_lock = asyncio.Lock()

        async def run_one(task: AsyncReadTask) -> None:
            nonlocal active, peak
            surface_sem = surface_sems.get(task.surface)

            async def body() -> None:
                nonlocal active, peak
                started = perf_counter()
                async with counter_lock:
                    active += 1
                    peak = max(peak, active)
                    surface_active[task.surface] = surface_active.get(task.surface, 0) + 1
                    surface_peak[task.surface] = max(
                        surface_peak.get(task.surface, 0), surface_active[task.surface]
                    )
                try:
                    async with asyncio.timeout(task.timeout_seconds):
                        value = await task.run()
                    state = "SUCCESS"
                    error_type = ""
                    error_message = ""
                except TimeoutError as exc:
                    value = None
                    state = "TIMEOUT"
                    error_type = type(exc).__name__
                    error_message = str(exc)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # captured into receipt; no orphaned task
                    value = None
                    state = "FAILED"
                    error_type = type(exc).__name__
                    error_message = str(exc)
                finally:
                    elapsed = int((perf_counter() - started) * 1000)
                    async with counter_lock:
                        active -= 1
                        surface_active[task.surface] -= 1
                results[task.task_id] = AsyncReadResult(
                    task.task_id, task.surface, state, elapsed, value, error_type, error_message
                )

            async with global_sem:
                if surface_sem is None:
                    await body()
                else:
                    async with surface_sem:
                        await body()

        async with asyncio.TaskGroup() as group:
            for task in tasks:
                group.create_task(run_one(task), name=f"cfbe:{task.surface}:{task.task_id}")

        ordered = tuple(results[t.task_id] for t in tasks)
        return StructuredExecutionReceipt(ordered, peak, tuple(sorted(surface_peak.items())))


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass(frozen=True, slots=True)
class CircuitPolicy:
    min_samples: int = 5
    failure_ratio_to_open: float = 0.5
    open_ticks: int = 3
    half_open_successes_to_close: int = 2

    def validate(self) -> None:
        if self.min_samples < 1 or self.open_ticks < 1 or self.half_open_successes_to_close < 1:
            raise ValueError("CIRCUIT_POLICY_COUNT_INVALID")
        if not 0 < self.failure_ratio_to_open <= 1:
            raise ValueError("CIRCUIT_FAILURE_RATIO_INVALID")


@dataclass(frozen=True, slots=True)
class CircuitSnapshot:
    route_id: str
    state: CircuitState
    samples: int
    failures: int
    opened_at_tick: int = -1
    half_open_successes: int = 0

    @property
    def failure_ratio(self) -> float:
        return (self.failures / self.samples) if self.samples else 0.0


class DynamicCircuitBreaker:
    """CLOSED→OPEN→HALF_OPEN→CLOSED route health state machine."""

    def __init__(self, policy: CircuitPolicy = CircuitPolicy()) -> None:
        policy.validate()
        self.policy = policy
        self._state: dict[str, CircuitSnapshot] = {}

    def snapshot(self, route_id: str, *, now_tick: int) -> CircuitSnapshot:
        if not route_id.strip() or now_tick < 0:
            raise ValueError("CIRCUIT_IDENTITY_OR_TIME_INVALID")
        current = self._state.get(route_id, CircuitSnapshot(route_id, CircuitState.CLOSED, 0, 0))
        if (
            current.state is CircuitState.OPEN
            and current.opened_at_tick >= 0
            and now_tick - current.opened_at_tick >= self.policy.open_ticks
        ):
            current = CircuitSnapshot(
                route_id, CircuitState.HALF_OPEN, current.samples, current.failures,
                current.opened_at_tick, 0
            )
            self._state[route_id] = current
        return current

    def allow(self, route_id: str, *, now_tick: int) -> bool:
        return self.snapshot(route_id, now_tick=now_tick).state is not CircuitState.OPEN

    def record(self, route_id: str, *, success: bool, now_tick: int) -> CircuitSnapshot:
        current = self.snapshot(route_id, now_tick=now_tick)
        if current.state is CircuitState.OPEN:
            return current

        if current.state is CircuitState.HALF_OPEN:
            if not success:
                updated = CircuitSnapshot(
                    route_id, CircuitState.OPEN, current.samples + 1, current.failures + 1,
                    now_tick, 0
                )
            else:
                successes = current.half_open_successes + 1
                if successes >= self.policy.half_open_successes_to_close:
                    updated = CircuitSnapshot(route_id, CircuitState.CLOSED, 0, 0, -1, 0)
                else:
                    updated = CircuitSnapshot(
                        route_id, CircuitState.HALF_OPEN, current.samples + 1, current.failures,
                        current.opened_at_tick, successes
                    )
            self._state[route_id] = updated
            return updated

        samples = current.samples + 1
        failures = current.failures + (0 if success else 1)
        ratio = failures / samples
        if samples >= self.policy.min_samples and ratio >= self.policy.failure_ratio_to_open:
            updated = CircuitSnapshot(route_id, CircuitState.OPEN, samples, failures, now_tick, 0)
        else:
            updated = CircuitSnapshot(route_id, CircuitState.CLOSED, samples, failures, -1, 0)
        self._state[route_id] = updated
        return updated


__all__ = [
    "AsyncReadResult",
    "AsyncReadTask",
    "CircuitPolicy",
    "CircuitSnapshot",
    "CircuitState",
    "DynamicCircuitBreaker",
    "SCHEMA",
    "StructuredExecutionReceipt",
    "StructuredReadExecutor",
    "VERSION",
]
