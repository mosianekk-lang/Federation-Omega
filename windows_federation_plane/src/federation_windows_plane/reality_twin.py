from __future__ import annotations

import hashlib
import math
import random
import statistics
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .substrate_contracts import ExecutorPassport, RoutingPolicy, WorkloadSpec


@dataclass
class ExecutorState:
    cpu_pressure: float = 0.0
    memory_pressure: float = 0.0
    queue_pressure: float = 0.0
    assignments: int = 0
    healthy: bool = True


@dataclass(frozen=True)
class Prediction:
    latency_ms: float
    failure_probability: float
    uncertainty: float


class _TinyMLP:
    """Small pure-stdlib MLP. It predicts latency-normalized and failure risk.

    It is intentionally a world-model only: it cannot mutate source, authority,
    capabilities, or promotion state. Training changes predictions, never policy gates.
    """

    def __init__(self, input_dim: int, hidden: int = 16, seed: int = 0) -> None:
        rng = random.Random(seed)
        self.w1 = [[rng.gauss(0.0, 0.12) for _ in range(hidden)] for _ in range(input_dim)]
        self.b1 = [0.0] * hidden
        self.w2 = [[rng.gauss(0.0, 0.12) for _ in range(2)] for _ in range(hidden)]
        self.b2 = [0.0, 0.0]

    @staticmethod
    def _sigmoid(x: float) -> float:
        x = max(-30.0, min(30.0, x))
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def _softplus(x: float) -> float:
        if x > 30.0:
            return x
        if x < -30.0:
            return math.exp(x)
        return math.log1p(math.exp(x))

    def _forward(self, x: Sequence[float]) -> Tuple[List[float], List[float], List[float]]:
        hidden: List[float] = []
        for j in range(len(self.b1)):
            z = self.b1[j] + sum(x[i] * self.w1[i][j] for i in range(len(x)))
            hidden.append(math.tanh(z))
        z2 = [
            self.b2[k] + sum(hidden[j] * self.w2[j][k] for j in range(len(hidden)))
            for k in range(2)
        ]
        return hidden, z2, [self._softplus(z2[0]), self._sigmoid(z2[1])]

    def predict(self, x: Sequence[float]) -> Tuple[float, float]:
        return tuple(self._forward(x)[2])  # type: ignore[return-value]

    def fit(self, xs: Sequence[Sequence[float]], ys: Sequence[Sequence[float]], *, steps: int = 90, lr: float = 0.02) -> None:
        if not xs:
            return
        for _ in range(steps):
            gw1 = [[0.0 for _ in row] for row in self.w1]
            gb1 = [0.0] * len(self.b1)
            gw2 = [[0.0, 0.0] for _ in self.w2]
            gb2 = [0.0, 0.0]
            n = float(len(xs))
            for x, y in zip(xs, ys):
                h, z, p = self._forward(x)
                dz = [0.0, 0.0]
                dz[0] = (2.0 * (p[0] - y[0]) * self._sigmoid(z[0])) / n
                dz[1] = (p[1] - y[1]) / n
                for j in range(len(h)):
                    for k in range(2):
                        gw2[j][k] += h[j] * dz[k]
                gb2[0] += dz[0]
                gb2[1] += dz[1]
                dh = [
                    (dz[0] * self.w2[j][0] + dz[1] * self.w2[j][1]) * (1.0 - h[j] * h[j])
                    for j in range(len(h))
                ]
                for i in range(len(x)):
                    for j in range(len(h)):
                        gw1[i][j] += x[i] * dh[j]
                for j in range(len(h)):
                    gb1[j] += dh[j]
            for i in range(len(self.w1)):
                for j in range(len(self.w1[i])):
                    self.w1[i][j] -= lr * gw1[i][j]
            for j in range(len(self.b1)):
                self.b1[j] -= lr * gb1[j]
                self.w2[j][0] -= lr * gw2[j][0]
                self.w2[j][1] -= lr * gw2[j][1]
            self.b2[0] -= lr * gb2[0]
            self.b2[1] -= lr * gb2[1]


class NeuralRealityModel:
    """Ensemble predictor with disagreement as epistemic uncertainty."""

    def __init__(self, input_dim: int = 24, seeds: Sequence[int] = (11, 29, 47)) -> None:
        self.models = [_TinyMLP(input_dim=input_dim, seed=seed) for seed in seeds]
        self.trained = False

    def fit(self, xs: Sequence[Sequence[float]], ys: Sequence[Sequence[float]]) -> None:
        for index, model in enumerate(self.models):
            if len(xs) <= 2:
                sample_x, sample_y = xs, ys
            else:
                order = list(range(len(xs)))
                order = order[index:] + order[:index]
                sample_x = [xs[i] for i in order]
                sample_y = [ys[i] for i in order]
            model.fit(sample_x, sample_y)
        self.trained = bool(xs)

    def predict(self, features: Sequence[float]) -> Prediction:
        values = [model.predict(features) for model in self.models]
        lat = [row[0] for row in values]
        fail = [row[1] for row in values]
        mean_lat = statistics.fmean(lat)
        mean_fail = statistics.fmean(fail)
        uncertainty = statistics.fmean(
            [statistics.pstdev(lat) if len(lat) > 1 else 0.0, statistics.pstdev(fail) if len(fail) > 1 else 0.0]
        )
        return Prediction(
            latency_ms=max(1.0, mean_lat * 1000.0),
            failure_probability=max(0.0, min(1.0, mean_fail)),
            uncertainty=max(0.0, uncertainty),
        )


def _features(executor: ExecutorPassport, workload: WorkloadSpec, state: ExecutorState) -> List[float]:
    r = workload.resources
    c = executor.capacity
    proof_rank = {
        "DISCOVERED": 0.0,
        "AUTHENTICATED": 0.2,
        "SOURCE_BOUND": 0.4,
        "EXECUTION_PROVEN": 0.6,
        "READBACK_PROVEN": 0.8,
        "PRODUCTION_ELIGIBLE": 1.0,
    }[executor.proof_maturity.value]
    return [
        executor.startup_ms / 1000.0,
        executor.isolation,
        executor.locality,
        executor.resilience,
        executor.energy_efficiency,
        executor.variable_cost,
        executor.privacy_fit,
        executor.residency_fit,
        executor.accelerator_score,
        executor.commercial.value_score(),
        proof_rank,
        r.cpu / max(1.0, c.cpu),
        r.memory_gb / max(1.0, c.memory_gb),
        r.gpu / max(1.0, c.gpu or 1.0),
        r.io / max(1.0, c.io or 1.0),
        r.network / max(1.0, c.network or 1.0),
        workload.latency_sensitivity,
        workload.resilience_need,
        workload.accelerator_affinity,
        workload.commercial_priority,
        state.cpu_pressure,
        state.memory_pressure,
        state.queue_pressure,
        1.0,
    ]


class CognitivePlacementEngine:
    """FILTER -> PREDICT -> SCORE -> BIND.

    Deterministic policy gates are authoritative. Neural predictions and adaptive
    policy weights may rank only candidates that have already passed hard gates.
    """

    def __init__(self, executors: Iterable[ExecutorPassport], world: NeuralRealityModel, policy: RoutingPolicy | None = None) -> None:
        self.executors = list(executors)
        self.world = world
        self.policy = (policy or RoutingPolicy()).normalized()
        self.state: Dict[str, ExecutorState] = {e.executor_id: ExecutorState() for e in self.executors}

    def feasible(self, executor: ExecutorPassport, workload: WorkloadSpec) -> bool:
        state = self.state[executor.executor_id]
        return (
            state.healthy
            and workload.required_capabilities.issubset(executor.capabilities)
            and executor.capacity.fits(workload.resources)
            and executor.isolation + 1e-12 >= workload.min_isolation
            and executor.privacy_fit + 1e-12 >= workload.min_privacy_fit
            and executor.residency_fit + 1e-12 >= workload.min_residency_fit
            and (not workload.allowed_executor_kinds or executor.kind in workload.allowed_executor_kinds)
        )

    def _stable_jitter(self, executor: ExecutorPassport, workload: WorkloadSpec) -> float:
        if self.policy.exploration <= 0.0:
            return 0.0
        digest = hashlib.sha256(f"{workload.workload_id}|{executor.executor_id}".encode("utf-8")).digest()
        unit = int.from_bytes(digest[:8], "big") / float((2**64) - 1)
        return ((unit - 0.5) * 2.0) * self.policy.exploration

    def score(self, executor: ExecutorPassport, workload: WorkloadSpec) -> float:
        p = self.policy
        state = self.state[executor.executor_id]
        pred = self.world.predict(_features(executor, workload, state))
        pressure = statistics.fmean((state.cpu_pressure, state.memory_pressure, state.queue_pressure))
        accel_gap = max(0.0, workload.accelerator_affinity - executor.accelerator_score)
        privacy_margin = min(executor.privacy_fit - workload.min_privacy_fit, executor.residency_fit - workload.min_residency_fit)
        commercial_gap = 1.0 - executor.commercial.value_score()
        spread = state.assignments / max(1.0, 1.0 + sum(s.assignments for s in self.state.values()))
        return (
            p.latency_weight * (pred.latency_ms / 1000.0) * max(0.2, workload.latency_sensitivity)
            + p.failure_weight * pred.failure_probability * max(0.3, workload.resilience_need)
            + p.pressure_weight * pressure
            + p.locality_weight * (1.0 - executor.locality)
            + p.energy_weight * (1.0 - executor.energy_efficiency)
            + p.accelerator_weight * accel_gap
            + p.cost_weight * executor.variable_cost
            + p.privacy_weight * max(0.0, 0.25 - privacy_margin)
            + p.commercial_weight * commercial_gap * workload.commercial_priority
            + p.uncertainty_weight * pred.uncertainty
            + p.spread_weight * spread
            + self._stable_jitter(executor, workload)
        )

    def choose(self, workload: WorkloadSpec) -> ExecutorPassport:
        candidates = [executor for executor in self.executors if self.feasible(executor, workload)]
        if not candidates:
            raise RuntimeError(f"NO_FEASIBLE_EXECUTOR:{workload.workload_id}")
        return min(candidates, key=lambda executor: (self.score(executor, workload), executor.executor_id))


@dataclass(frozen=True)
class TwinResult:
    completed: int
    failures: int
    safety_violations: int
    mean_latency_ms: float
    total_cost: float
    commercial_value: float
    score: float


class DeterministicRealityTwin:
    """Discrete workload twin for safe placement and failure/capacity rehearsal."""

    def __init__(self, executors: Iterable[ExecutorPassport], world: NeuralRealityModel, policy: RoutingPolicy | None = None, *, seed: int = 7) -> None:
        self.executors = list(executors)
        self.world = world
        self.engine = CognitivePlacementEngine(self.executors, world, policy)
        self.rng = random.Random(seed)

    def _physical_estimate(self, executor: ExecutorPassport, workload: WorkloadSpec) -> Tuple[float, float]:
        state = self.engine.state[executor.executor_id]
        r = workload.resources
        load = 1.0 + 0.90 * state.cpu_pressure + 0.70 * state.memory_pressure + 0.65 * state.queue_pressure
        resource = 0.050 * r.cpu + 0.028 * r.memory_gb + 0.130 * r.gpu + 0.020 * r.io + 0.020 * r.network
        acceleration = max(0.30, 1.0 - (0.55 * min(workload.accelerator_affinity, executor.accelerator_score)))
        latency = max(2.0, (executor.startup_ms + (1000.0 * resource * load)) * acceleration)
        fail = 0.003 + ((1.0 - executor.resilience) * 0.10)
        fail += max(0.0, state.cpu_pressure - 0.88) * 0.40
        fail += max(0.0, state.memory_pressure - 0.90) * 0.50
        return latency, min(0.98, max(0.0, fail))

    def run(self, workloads: Sequence[WorkloadSpec]) -> TwinResult:
        completed = failures = safety = 0
        latencies: List[float] = []
        total_cost = 0.0
        commercial_values: List[float] = []
        for workload in workloads:
            try:
                executor = self.engine.choose(workload)
            except RuntimeError:
                failures += 1
                continue
            state = self.engine.state[executor.executor_id]
            if not self.engine.feasible(executor, workload):
                safety += 1
                failures += 1
                continue
            latency, fail_probability = self._physical_estimate(executor, workload)
            failed = self.rng.random() < fail_probability
            state.assignments += 1
            state.cpu_pressure = min(1.0, state.cpu_pressure + (0.02 * workload.resources.cpu / max(1.0, executor.capacity.cpu)))
            state.memory_pressure = min(1.0, state.memory_pressure + (0.02 * workload.resources.memory_gb / max(1.0, executor.capacity.memory_gb)))
            state.queue_pressure = max(0.0, min(1.0, state.queue_pressure + 0.02))
            total_cost += executor.variable_cost * max(1.0, latency / 1000.0)
            commercial_values.append(executor.commercial.value_score())
            if failed:
                failures += 1
            else:
                completed += 1
                latencies.append(latency)
        mean_latency = statistics.fmean(latencies) if latencies else 1e9
        commercial_value = statistics.fmean(commercial_values) if commercial_values else 0.0
        total = max(1, len(workloads))
        score = (
            mean_latency / 1000.0
            + 2.5 * (failures / total)
            + 12.0 * (safety / total)
            + total_cost
            + 0.8 * (1.0 - commercial_value)
        )
        return TwinResult(completed, failures, safety, mean_latency, total_cost, commercial_value, score)


def make_training_set(executors: Sequence[ExecutorPassport], workloads: Sequence[WorkloadSpec]) -> Tuple[List[List[float]], List[List[float]]]:
    """Generate deterministic synthetic telemetry for cold-start world-model training.

    Promotion still requires real provider/device telemetry; these samples are only a
    cold-start prior so the scheduler can be tested before a physical surface exists.
    """
    xs: List[List[float]] = []
    ys: List[List[float]] = []
    dummy = NeuralRealityModel()
    twin = DeterministicRealityTwin(executors, dummy, RoutingPolicy(exploration=0.0), seed=3)
    for executor in executors:
        for workload in workloads:
            if not twin.engine.feasible(executor, workload):
                continue
            for pressure in (0.05, 0.35, 0.70, 0.92):
                state = twin.engine.state[executor.executor_id]
                state.cpu_pressure = pressure
                state.memory_pressure = min(1.0, pressure * 0.92)
                state.queue_pressure = min(1.0, pressure * 0.78)
                latency, fail = twin._physical_estimate(executor, workload)
                xs.append(_features(executor, workload, state))
                ys.append([latency / 1000.0, fail])
    return xs, ys


def evolve_policy(
    executors: Sequence[ExecutorPassport],
    world: NeuralRealityModel,
    workloads: Sequence[WorkloadSpec],
    incumbent: RoutingPolicy,
    *,
    generations: int = 3,
    population: int = 12,
    seed: int = 17,
) -> Tuple[RoutingPolicy, float, bool]:
    """Bounded evolutionary search over routing weights, never over executable code.

    A candidate can promote only when the deterministic twin reports zero safety
    violations and its score beats the incumbent. Physical promotion remains a
    separate proof lane.
    """
    rng = random.Random(seed)
    base = incumbent.normalized()
    baseline = DeterministicRealityTwin(executors, world, base, seed=seed).run(workloads)
    best_policy = base
    best_result = baseline
    weight_names = [name for name in RoutingPolicy.__dataclass_fields__ if name != "exploration"]
    for _ in range(max(1, generations)):
        candidates: List[RoutingPolicy] = []
        for _ in range(max(2, population)):
            payload = {name: max(0.01, getattr(best_policy, name) * rng.uniform(0.70, 1.30)) for name in weight_names}
            payload["exploration"] = max(0.0, min(0.20, best_policy.exploration * rng.uniform(0.5, 1.5)))
            candidates.append(RoutingPolicy(**payload).normalized())
        for candidate in candidates:
            result = DeterministicRealityTwin(executors, world, candidate, seed=seed).run(workloads)
            if result.safety_violations == 0 and result.score < best_result.score:
                best_policy, best_result = candidate, result
    promoted = best_result.safety_violations == 0 and best_result.score < baseline.score
    return best_policy, best_result.score, promoted
