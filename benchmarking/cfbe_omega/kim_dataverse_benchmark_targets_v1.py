from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkTarget:
    metric: str
    level5_target: float
    level7_target: float
    level8_target: float
    direction: str


TARGETS = (
    BenchmarkTarget("verified_completion_rate", 0.90, 0.98, 0.99, "HIGHER"),
    BenchmarkTarget("avoidable_owner_interruption_rate", 0.20, 0.05, 0.02, "LOWER"),
    BenchmarkTarget("maintenance_self_resolution_rate", 0.80, 0.95, 0.98, "HIGHER"),
    BenchmarkTarget("recovery_self_resolution_rate", 0.80, 0.95, 0.98, "HIGHER"),
    BenchmarkTarget("chat_dependency_rate", 0.20, 0.00, 0.00, "LOWER"),
    BenchmarkTarget("global_stall_rate", 0.05, 0.00, 0.00, "LOWER"),
)


def benchmark_targets() -> tuple[BenchmarkTarget, ...]:
    return TARGETS
