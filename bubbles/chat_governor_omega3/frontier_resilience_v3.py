from __future__ import annotations

"""ChatGov/FUSE frontier resilience controls v3.

A bounded, provider-neutral resilience tranche subordinate to the existing
ChatGov/FUSE/SOVARA/ProofOS planes.  It adds fault-isolation and overload-control
mechanisms without executing provider effects or minting authority:

* power-of-two load selection among already-qualified replicas/routes;
* statistical/consecutive-failure outlier quarantine recommendations;
* deterministic shuffle-shard flow isolation;
* deadline-budget compilation with proof/finalization reserves;
* graceful degradation that preserves authority/proof/readback controls;
* deterministic chaos-court compilation for UAS qualification.

Actual routing changes, ejections, deployments, fault injection and provider
traffic remain external effects and must use existing authorized execution paths.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import statistics
from typing import Any, Mapping, Sequence


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str)


def _digest(value: Any) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _finite(value: float, name: str, *, minimum: float = 0.0) -> float:
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name}_INVALID")
    return value


@dataclass(frozen=True, slots=True)
class ReplicaLoad:
    replica_id: str
    active_requests: int
    weight: float = 1.0
    healthy: bool = True
    qualified: bool = True
    ejected: bool = False

    def validate(self) -> "ReplicaLoad":
        if not self.replica_id.strip() or self.active_requests < 0:
            raise ValueError("REPLICA_LOAD_INVALID")
        if not math.isfinite(float(self.weight)) or self.weight <= 0:
            raise ValueError("REPLICA_WEIGHT_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class ReplicaSelection:
    selected: str
    sampled: tuple[str, ...]
    reason: str


class PowerOfTwoLoadSelector:
    """Load-aware selection inside an already-qualified route set.

    Deterministic hashing supplies the small candidate sample; the least-loaded
    qualified member wins. This is not a quality/proof route ranker and therefore
    composes after CFBE proof-weighted eligibility rather than replacing it.
    """

    def __init__(self, *, choice_count: int = 2, active_request_bias: float = 1.0) -> None:
        if choice_count < 1 or not math.isfinite(float(active_request_bias)) or active_request_bias < 0:
            raise ValueError("P2C_POLICY_INVALID")
        self.choice_count = int(choice_count)
        self.active_request_bias = float(active_request_bias)

    def choose(self, *, request_key: str, replicas: Sequence[ReplicaLoad]) -> ReplicaSelection:
        if not request_key.strip():
            raise ValueError("P2C_REQUEST_KEY_REQUIRED")
        eligible = [row.validate() for row in replicas if row.healthy and row.qualified and not row.ejected]
        if not eligible:
            raise ValueError("P2C_NO_ELIGIBLE_REPLICA")
        ranked = sorted(
            eligible,
            key=lambda row: _digest({"request": request_key, "replica": row.replica_id}),
        )
        sampled = ranked[: min(self.choice_count, len(ranked))]

        def score(row: ReplicaLoad) -> tuple[float, str]:
            effective_weight = float(row.weight) / ((row.active_requests + 1) ** self.active_request_bias)
            return (-effective_weight, row.replica_id)

        selected = min(sampled, key=score)
        return ReplicaSelection(selected.replica_id, tuple(row.replica_id for row in sampled), "QUALIFIED_POWER_OF_N_LEAST_LOAD")


@dataclass(frozen=True, slots=True)
class ProviderHealthSample:
    provider_id: str
    successes: int
    trials: int
    consecutive_gateway_failures: int = 0
    consecutive_local_failures: int = 0
    p95_latency_ms: float = 0.0
    currently_ejected: bool = False

    def validate(self) -> "ProviderHealthSample":
        if not self.provider_id.strip() or self.trials < 0 or self.successes < 0 or self.successes > self.trials:
            raise ValueError("OUTLIER_SAMPLE_INVALID")
        if self.consecutive_gateway_failures < 0 or self.consecutive_local_failures < 0:
            raise ValueError("OUTLIER_CONSECUTIVE_FAILURE_INVALID")
        _finite(self.p95_latency_ms, "OUTLIER_LATENCY")
        return self

    @property
    def success_rate(self) -> float:
        return 1.0 if self.trials == 0 else self.successes / self.trials


@dataclass(frozen=True, slots=True)
class OutlierAction:
    provider_id: str
    action: str
    reason: str
    success_rate: float


class ProviderOutlierGovernor:
    """Passive-health quarantine recommendations with blast-radius caps."""

    def __init__(
        self,
        *,
        min_request_volume: int = 50,
        success_rate_stdev_factor: float = 1.9,
        consecutive_gateway_failure_threshold: int = 5,
        consecutive_local_failure_threshold: int = 5,
        max_ejection_fraction: float = 0.50,
        min_healthy_providers: int = 1,
    ) -> None:
        if min_request_volume < 1 or success_rate_stdev_factor < 0:
            raise ValueError("OUTLIER_POLICY_INVALID")
        if consecutive_gateway_failure_threshold < 1 or consecutive_local_failure_threshold < 1:
            raise ValueError("OUTLIER_FAILURE_THRESHOLD_INVALID")
        if not 0 < max_ejection_fraction <= 1 or min_healthy_providers < 1:
            raise ValueError("OUTLIER_BLAST_RADIUS_POLICY_INVALID")
        self.min_request_volume = int(min_request_volume)
        self.success_rate_stdev_factor = float(success_rate_stdev_factor)
        self.gateway_threshold = int(consecutive_gateway_failure_threshold)
        self.local_threshold = int(consecutive_local_failure_threshold)
        self.max_ejection_fraction = float(max_ejection_fraction)
        self.min_healthy_providers = int(min_healthy_providers)

    def evaluate(self, samples: Sequence[ProviderHealthSample]) -> tuple[OutlierAction, ...]:
        rows = [row.validate() for row in samples]
        if not rows:
            return ()
        eligible_stats = [row.success_rate for row in rows if row.trials >= self.min_request_volume and not row.currently_ejected]
        mean = statistics.fmean(eligible_stats) if eligible_stats else 1.0
        stdev = statistics.pstdev(eligible_stats) if len(eligible_stats) > 1 else 0.0
        success_floor = mean - self.success_rate_stdev_factor * stdev

        candidates: list[tuple[float, ProviderHealthSample, str]] = []
        actions: dict[str, OutlierAction] = {}
        for row in rows:
            if row.currently_ejected:
                recovered = (
                    row.trials >= self.min_request_volume
                    and row.consecutive_gateway_failures == 0
                    and row.consecutive_local_failures == 0
                    and row.success_rate >= success_floor
                )
                actions[row.provider_id] = OutlierAction(
                    row.provider_id,
                    "PROBE_REINSTATE" if recovered else "KEEP_EJECTED",
                    "RECOVERY_PROBE_ELIGIBLE" if recovered else "RECOVERY_NOT_YET_PROVEN",
                    row.success_rate,
                )
                continue

            reasons: list[str] = []
            severity = 0.0
            if row.consecutive_gateway_failures >= self.gateway_threshold:
                reasons.append("CONSECUTIVE_GATEWAY_FAILURE")
                severity += row.consecutive_gateway_failures / self.gateway_threshold
            if row.consecutive_local_failures >= self.local_threshold:
                reasons.append("CONSECUTIVE_LOCAL_FAILURE")
                severity += row.consecutive_local_failures / self.local_threshold
            if row.trials >= self.min_request_volume and row.success_rate < success_floor:
                reasons.append("SUCCESS_RATE_STATISTICAL_OUTLIER")
                severity += max(0.0, success_floor - row.success_rate) * 10.0
            if reasons:
                candidates.append((severity, row, "+".join(reasons)))
            else:
                actions[row.provider_id] = OutlierAction(row.provider_id, "KEEP", "NO_OUTLIER_SIGNAL", row.success_rate)

        active_count = sum(1 for row in rows if not row.currently_ejected)
        cap_by_fraction = max(0, math.floor(len(rows) * self.max_ejection_fraction) - sum(1 for row in rows if row.currently_ejected))
        cap_by_health = max(0, active_count - self.min_healthy_providers)
        allowed = min(cap_by_fraction, cap_by_health)
        for rank, (_, row, reason) in enumerate(sorted(candidates, key=lambda item: (-item[0], item[1].provider_id))):
            if rank < allowed:
                actions[row.provider_id] = OutlierAction(row.provider_id, "EJECT_RECOMMENDED", reason, row.success_rate)
            else:
                actions[row.provider_id] = OutlierAction(row.provider_id, "KEEP_BLAST_RADIUS_CAP", "OUTLIER_SIGNAL_BUT_EJECTION_CAP_REACHED", row.success_rate)
        return tuple(actions[key] for key in sorted(actions))


@dataclass(frozen=True, slots=True)
class ShuffleShardPlan:
    flow_id: str
    queue_indices: tuple[int, ...]
    shard_digest: str


class ShuffleShardPlanner:
    """Stable small-subset queue isolation for noisy-neighbor containment."""

    def __init__(self, *, queue_count: int, shard_size: int, salt: str = "FUSE") -> None:
        if queue_count < 2 or shard_size < 1 or shard_size > queue_count or not salt.strip():
            raise ValueError("SHUFFLE_SHARD_POLICY_INVALID")
        self.queue_count = int(queue_count)
        self.shard_size = int(shard_size)
        self.salt = salt

    def plan(self, flow_id: str) -> ShuffleShardPlan:
        if not flow_id.strip():
            raise ValueError("SHUFFLE_SHARD_FLOW_REQUIRED")
        ranked = sorted(
            range(self.queue_count),
            key=lambda idx: _digest({"salt": self.salt, "flow": flow_id, "queue": idx}),
        )
        shard = tuple(sorted(ranked[: self.shard_size]))
        return ShuffleShardPlan(flow_id, shard, _digest({"flow": flow_id, "queues": shard, "salt": self.salt}))


@dataclass(frozen=True, slots=True)
class DeadlineStage:
    stage_id: str
    p95_ms: float
    required: bool
    value_score: float = 1.0

    def validate(self) -> "DeadlineStage":
        if not self.stage_id.strip():
            raise ValueError("DEADLINE_STAGE_ID_REQUIRED")
        _finite(self.p95_ms, "DEADLINE_STAGE_P95", minimum=0.001)
        if not 0.0 <= float(self.value_score) <= 1.0:
            raise ValueError("DEADLINE_STAGE_VALUE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class StageBudget:
    stage_id: str
    budget_ms: float
    required: bool


@dataclass(frozen=True, slots=True)
class DeadlinePlan:
    mode: str
    selected: tuple[StageBudget, ...]
    omitted_optional: tuple[str, ...]
    proof_reserve_ms: float
    final_reserve_ms: float
    total_budget_ms: float
    reason: str


class DeadlineBudgetCompiler:
    """Allocate finite mission time while reserving proof and finalization."""

    def compile(
        self,
        *,
        total_budget_ms: float,
        stages: Sequence[DeadlineStage],
        proof_reserve_ms: float,
        final_reserve_ms: float,
    ) -> DeadlinePlan:
        total = _finite(total_budget_ms, "DEADLINE_TOTAL", minimum=0.001)
        proof = _finite(proof_reserve_ms, "DEADLINE_PROOF_RESERVE")
        final = _finite(final_reserve_ms, "DEADLINE_FINAL_RESERVE")
        rows = [row.validate() for row in stages]
        if len({row.stage_id for row in rows}) != len(rows):
            raise ValueError("DEADLINE_STAGE_DUPLICATE")
        available = total - proof - final
        required = [row for row in rows if row.required]
        optional = [row for row in rows if not row.required]
        required_cost = sum(row.p95_ms for row in required)
        if available < required_cost:
            return DeadlinePlan(
                "HOLD_UNSATISFIABLE",
                (),
                tuple(sorted(row.stage_id for row in optional)),
                proof,
                final,
                total,
                "REQUIRED_STAGES_PLUS_PROOF_EXCEED_DEADLINE",
            )
        selected = list(required)
        remaining = available - required_cost
        optional.sort(key=lambda row: (-(row.value_score / row.p95_ms), row.stage_id))
        omitted: list[str] = []
        for row in optional:
            if row.p95_ms <= remaining:
                selected.append(row)
                remaining -= row.p95_ms
            else:
                omitted.append(row.stage_id)
        selected.sort(key=lambda row: row.stage_id)
        return DeadlinePlan(
            "FULL" if not omitted else "DEADLINE_TRIMMED",
            tuple(StageBudget(row.stage_id, row.p95_ms, row.required) for row in selected),
            tuple(sorted(omitted)),
            proof,
            final,
            total,
            "ALL_STAGES_FIT" if not omitted else "LOWER_VALUE_OPTIONAL_STAGES_OMITTED",
        )


@dataclass(frozen=True, slots=True)
class DegradationDecision:
    mode: str
    allowed_features: tuple[str, ...]
    disabled_features: tuple[str, ...]
    reason: str


class GracefulDegradationGovernor:
    """Reduce optional work under pressure without weakening proof or authority."""

    REQUIRED = frozenset({"policy_gate", "proof_readback", "failure_recording", "required_context"})
    OPTIONAL = (
        "secondary_research",
        "extra_challengers",
        "verbose_progress",
        "noncritical_enrichment",
        "read_hedging",
    )

    def decide(self, *, queue_utilization: float, p95_latency_ratio: float, error_rate: float) -> DegradationDecision:
        q = _finite(queue_utilization, "DEGRADE_QUEUE")
        l = _finite(p95_latency_ratio, "DEGRADE_LATENCY")
        e = _finite(error_rate, "DEGRADE_ERROR")
        pressure = max(q, l, min(2.0, e * 10.0))
        if pressure < 0.70:
            mode = "FULL_SERVICE"
            disabled: tuple[str, ...] = ()
        elif pressure < 1.0:
            mode = "DEGRADED"
            disabled = ("verbose_progress", "noncritical_enrichment")
        else:
            mode = "SURVIVAL"
            disabled = self.OPTIONAL
        allowed = tuple(sorted(self.REQUIRED | (set(self.OPTIONAL) - set(disabled))))
        return DegradationDecision(mode, allowed, tuple(disabled), "PRESSURE_GOVERNED_OPTIONAL_WORK_REDUCTION")


@dataclass(frozen=True, slots=True)
class ChaosScenario:
    scenario_id: str
    target: str
    fault: str
    expected_invariant: str
    sandbox_required: bool


@dataclass(frozen=True, slots=True)
class ChaosCourt:
    mission_class: str
    scenarios: tuple[ChaosScenario, ...]
    court_digest: str
    provider_effect_authorized: bool


class ChaosCourtCompiler:
    """Compile deterministic fault cases; never inject faults itself."""

    BASE_FAULTS = (
        ("WORKER_CRASH_AFTER_CHECKPOINT", "MISSION_RESUMES_WITHOUT_RECOMPUTING_PROVEN_SIBLINGS"),
        ("OUT_OF_ORDER_COMPLETION", "FINAL_PROOF_PROJECTION_REMAINS_DETERMINISTIC"),
        ("DUPLICATE_DELIVERY", "IDEMPOTENCY_PREVENTS_DUPLICATE_COMMIT"),
        ("STALE_READ", "FRESHNESS_GATE_REJECTS_STALE_EVIDENCE"),
        ("POLICY_DENIAL", "EFFECT_DOES_NOT_DISPATCH"),
    )

    def compile(
        self,
        *,
        mission_class: str,
        dependencies: Sequence[str],
        effectful: bool,
    ) -> ChaosCourt:
        if not mission_class.strip():
            raise ValueError("CHAOS_MISSION_CLASS_REQUIRED")
        deps = tuple(sorted({str(dep).strip() for dep in dependencies if str(dep).strip()}))
        scenarios: list[ChaosScenario] = []
        for dep in deps:
            for fault, invariant in (
                ("TIMEOUT", "UNRELATED_SAFE_LANES_CONTINUE_AND_ROUTE_CHANGES_OR_HOLDS"),
                ("UNAVAILABLE", "DEPENDENCY_FAILURE_IS_ISOLATED_AND_EXPLICIT"),
                ("THROTTLED", "RETRY_BUDGET_AND_BACKPRESSURE_PREVENT_STORM"),
            ):
                sid = "CHAOS-" + _digest({"mission": mission_class, "target": dep, "fault": fault})[:16]
                scenarios.append(ChaosScenario(sid, dep, fault, invariant, effectful))
        for fault, invariant in self.BASE_FAULTS:
            sid = "CHAOS-" + _digest({"mission": mission_class, "target": "MISSION", "fault": fault})[:16]
            scenarios.append(ChaosScenario(sid, "MISSION", fault, invariant, effectful))
        if effectful:
            for fault, invariant in (
                ("PROVIDER_READBACK_MISMATCH", "MISSION_CANNOT_PROMOTE_EFFECT_TO_VERIFIED"),
                ("EFFECT_UNCERTAIN_AFTER_DISPATCH", "STATE_HOLDS_FAILED_UNCERTAIN_WITHOUT_BLIND_RETRY"),
            ):
                sid = "CHAOS-" + _digest({"mission": mission_class, "target": "EFFECT", "fault": fault})[:16]
                scenarios.append(ChaosScenario(sid, "EFFECT", fault, invariant, True))
        material = [
            {"id": row.scenario_id, "target": row.target, "fault": row.fault, "invariant": row.expected_invariant, "sandbox": row.sandbox_required}
            for row in scenarios
        ]
        return ChaosCourt(mission_class, tuple(scenarios), _digest(material), False)


@dataclass(frozen=True, slots=True)
class FrontierResilienceV3Receipt:
    schema: str
    capabilities: tuple[str, ...]
    provider_effect_authorized: bool
    fault_injection_authorized: bool
    route_ejection_authorized: bool


def frontier_resilience_v3_receipt() -> FrontierResilienceV3Receipt:
    return FrontierResilienceV3Receipt(
        "CHATGOV-FRONTIER-RESILIENCE-V3",
        (
            "QUALIFIED_POWER_OF_TWO_LOAD_SELECTION",
            "PASSIVE_PROVIDER_OUTLIER_QUARANTINE_POLICY",
            "DETERMINISTIC_SHUFFLE_SHARD_FLOW_ISOLATION",
            "PROOF_RESERVED_DEADLINE_BUDGET_COMPILATION",
            "GRACEFUL_DEGRADATION_WITH_PROOF_PRESERVATION",
            "DETERMINISTIC_UAS_CHAOS_COURT_COMPILATION",
        ),
        False,
        False,
        False,
    )


__all__ = [
    "ChaosCourt",
    "ChaosCourtCompiler",
    "ChaosScenario",
    "DeadlineBudgetCompiler",
    "DeadlinePlan",
    "DeadlineStage",
    "DegradationDecision",
    "FrontierResilienceV3Receipt",
    "GracefulDegradationGovernor",
    "OutlierAction",
    "PowerOfTwoLoadSelector",
    "ProviderHealthSample",
    "ProviderOutlierGovernor",
    "ReplicaLoad",
    "ReplicaSelection",
    "ShuffleShardPlan",
    "ShuffleShardPlanner",
    "StageBudget",
    "frontier_resilience_v3_receipt",
]
