from __future__ import annotations

from dataclasses import dataclass, asdict

from .evolution import PerformanceVector, fitness


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    useful_outputs: int
    defects_caught_before_owner: int
    owner_interruptions: int
    resource_calls: int
    blocked_independent_nodes: int
    stale_dependencies_flagged: int
    latency_units: float

    def fitness_vector(self) -> PerformanceVector:
        return PerformanceVector(
            quality=float(self.useful_outputs + self.defects_caught_before_owner),
            reliability=float(self.defects_caught_before_owner + 1),
            proof=float(self.stale_dependencies_flagged + 1),
            speed=max(0.0, 10.0 - self.latency_units),
            owner_time_recovered=max(0.0, 5.0 - self.owner_interruptions),
            recovery_gain=max(0.0, 3.0 - self.blocked_independent_nodes),
            simplicity_gain=max(0.0, 10.0 - self.resource_calls),
            false_blocks=float(self.blocked_independent_nodes),
            latency_cost=self.latency_units,
            owner_burden=float(self.owner_interruptions),
            complexity=float(self.resource_calls) / 2.0,
        )


class V2ReferencePolicy:
    """Synthetic deterministic representation of the v2 prompt-style baseline.

    It is NOT a measurement of any deployed v2 provider runtime. The fixture
    captures known architectural differences only: broader resource fan-out,
    conversation-led serial blocking, no formal proof-dependency propagation,
    and more owner interruption.
    """

    def run(self) -> BenchmarkResult:
        return BenchmarkResult(
            name="V2_REFERENCE_SYNTHETIC",
            useful_outputs=3,
            defects_caught_before_owner=1,
            owner_interruptions=2,
            resource_calls=8,
            blocked_independent_nodes=2,
            stale_dependencies_flagged=0,
            latency_units=6.0,
        )


class V3FabricPolicy:
    """Synthetic deterministic fixture exercising v3 structural controls."""

    def run(self) -> BenchmarkResult:
        return BenchmarkResult(
            name="V3_FABRIC_SYNTHETIC",
            useful_outputs=4,
            defects_caught_before_owner=3,
            owner_interruptions=0,
            resource_calls=3,
            blocked_independent_nodes=0,
            stale_dependencies_flagged=2,
            latency_units=2.5,
        )


def run_benchmark() -> dict[str, object]:
    v2 = V2ReferencePolicy().run()
    v3 = V3FabricPolicy().run()
    v2_fitness = fitness(v2.fitness_vector())
    v3_fitness = fitness(v3.fitness_vector())
    return {
        "truth_boundary": "SYNTHETIC_DETERMINISTIC_ARCHITECTURE_BENCHMARK_NOT_PROVIDER_RUNTIME_PROOF",
        "v2": asdict(v2),
        "v3": asdict(v3),
        "v2_fitness": v2_fitness,
        "v3_fitness": v3_fitness,
        "delta": v3_fitness - v2_fitness,
        "v3_wins": v3_fitness > v2_fitness,
    }
