from __future__ import annotations

"""ChatGov/FUSE frontier runtime controls v2.

This module is subordinate to the existing ChatGov/FUSE control plane.  It adds
production-evolution and efficiency controls harvested at mechanism level from
modern durable execution / serving systems without introducing another
orchestrator or authority plane:

* content/dependency-addressed reuse for incremental recomputation;
* queue-pressure admission, priority ageing and optional-work load shedding;
* evidence-gated generation canary/ramp/rollback decisions;
* checkpoint-only mission generation upgrades;
* matched-context causal ablation for capability credit assignment;
* an admission gate for the already-existing SLOS read-only hedge runtime.

No class here executes provider effects, changes traffic, deploys a generation or
mints authority. Hosts must perform those effects through the existing SOVARA/SOL
admission path and prove provider-native readback separately.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence


NO_EFFECT_CLASSES = frozenset({"NO_EFFECT", "READ_ONLY", "PURE_COMPUTE"})


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _finite_nonnegative(value: float, name: str) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name}_INVALID")
    return value


@dataclass(frozen=True, slots=True)
class ProvenNodeResult:
    node_id: str
    fingerprint: str
    result_ref: str
    result_sha256: str
    proof_ref: str
    source_version: str


class DependencyResultCache:
    """Content-addressed incremental work cache.

    A node result is reusable only when its own input, code/source version and every
    dependency result digest are identical. This deliberately models build-system
    style incremental recomputation rather than TTL-only caching.
    """

    def __init__(self) -> None:
        self._entries: dict[str, ProvenNodeResult] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def fingerprint(
        *,
        node_id: str,
        input_payload: Any,
        dependency_result_sha256s: Mapping[str, str],
        code_version: str,
        source_version: str,
    ) -> str:
        if not all(str(x).strip() for x in (node_id, code_version, source_version)):
            raise ValueError("DEPENDENCY_CACHE_IDENTITY_REQUIRED")
        deps = {str(k): str(v) for k, v in sorted(dependency_result_sha256s.items())}
        if any(not k or not v for k, v in deps.items()):
            raise ValueError("DEPENDENCY_CACHE_DIGEST_REQUIRED")
        return _digest(
            {
                "node_id": node_id,
                "input_payload": input_payload,
                "dependencies": deps,
                "code_version": code_version,
                "source_version": source_version,
            }
        )

    def put(
        self,
        *,
        node_id: str,
        input_payload: Any,
        dependency_result_sha256s: Mapping[str, str],
        code_version: str,
        source_version: str,
        result_ref: str,
        result: Any,
        proof_ref: str,
        effect_class: str = "PURE_COMPUTE",
    ) -> ProvenNodeResult:
        if effect_class not in NO_EFFECT_CLASSES:
            raise ValueError("DEPENDENCY_CACHE_EFFECTFUL_RESULT_FORBIDDEN")
        if not result_ref.strip() or not proof_ref.strip():
            raise ValueError("DEPENDENCY_CACHE_PROOF_AND_RESULT_REF_REQUIRED")
        fp = self.fingerprint(
            node_id=node_id,
            input_payload=input_payload,
            dependency_result_sha256s=dependency_result_sha256s,
            code_version=code_version,
            source_version=source_version,
        )
        item = ProvenNodeResult(
            node_id=node_id,
            fingerprint=fp,
            result_ref=result_ref,
            result_sha256=_digest(result),
            proof_ref=proof_ref,
            source_version=source_version,
        )
        prior = self._entries.get(fp)
        if prior is not None and prior != item:
            raise ValueError("DEPENDENCY_CACHE_FINGERPRINT_CONFLICT")
        self._entries[fp] = item
        return item

    def get(
        self,
        *,
        node_id: str,
        input_payload: Any,
        dependency_result_sha256s: Mapping[str, str],
        code_version: str,
        source_version: str,
    ) -> ProvenNodeResult | None:
        fp = self.fingerprint(
            node_id=node_id,
            input_payload=input_payload,
            dependency_result_sha256s=dependency_result_sha256s,
            code_version=code_version,
            source_version=source_version,
        )
        item = self._entries.get(fp)
        if item is None:
            self.misses += 1
            return None
        self.hits += 1
        return item


@dataclass(frozen=True, slots=True)
class AdmissionTask:
    task_id: str
    priority: int
    age_seconds: float
    deadline_slack_seconds: float | None
    required: bool
    value_score: float

    def validate(self) -> "AdmissionTask":
        if not self.task_id.strip():
            raise ValueError("ADMISSION_TASK_ID_REQUIRED")
        if not 0 <= int(self.priority) <= 100:
            raise ValueError("ADMISSION_PRIORITY_OUT_OF_RANGE")
        _finite_nonnegative(self.age_seconds, "ADMISSION_AGE")
        if self.deadline_slack_seconds is not None:
            _finite_nonnegative(self.deadline_slack_seconds, "ADMISSION_DEADLINE_SLACK")
        if not 0.0 <= float(self.value_score) <= 1.0:
            raise ValueError("ADMISSION_VALUE_OUT_OF_RANGE")
        return self


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    action: str
    effective_priority: float
    retry_after_seconds: float
    reason: str


class QueuePressureGovernor:
    """Backpressure / load-shedding policy for bounded host execution.

    Required work is never silently discarded. Optional low-value work may be shed
    before the queue grows without bound. The class emits decisions only; it does
    not enqueue, cancel or execute tasks.
    """

    def __init__(
        self,
        *,
        max_ongoing: int,
        max_queued: int,
        optional_shed_score: float = 70.0,
    ) -> None:
        if max_ongoing < 1 or max_queued < 0:
            raise ValueError("ADMISSION_CAPACITY_INVALID")
        self.max_ongoing = int(max_ongoing)
        self.max_queued = int(max_queued)
        self.optional_shed_score = float(optional_shed_score)

    @staticmethod
    def effective_priority(task: AdmissionTask) -> float:
        task.validate()
        ageing = min(25.0, math.log1p(float(task.age_seconds)) * 3.0)
        deadline = 0.0
        if task.deadline_slack_seconds is not None:
            slack = float(task.deadline_slack_seconds)
            deadline = 40.0 / (1.0 + slack)
        required = 25.0 if task.required else 0.0
        value = float(task.value_score) * 20.0
        return float(task.priority) + ageing + deadline + required + value

    def decide(
        self,
        task: AdmissionTask,
        *,
        ongoing: int,
        queued: int,
        observed_service_seconds: float = 1.0,
    ) -> AdmissionDecision:
        task.validate()
        if ongoing < 0 or queued < 0:
            raise ValueError("ADMISSION_PRESSURE_NEGATIVE")
        service = max(0.001, _finite_nonnegative(observed_service_seconds, "ADMISSION_SERVICE"))
        score = self.effective_priority(task)

        if ongoing < self.max_ongoing:
            return AdmissionDecision("ADMIT_NOW", score, 0.0, "EXECUTION_SLOT_AVAILABLE")

        if not task.required and score < self.optional_shed_score:
            return AdmissionDecision("SHED_OPTIONAL", score, service, "OPTIONAL_LOW_VALUE_UNDER_PRESSURE")

        if queued < self.max_queued:
            ahead = max(1, queued + 1)
            retry_after = service * ahead / self.max_ongoing
            return AdmissionDecision("QUEUE_BOUNDED", score, retry_after, "BOUNDED_QUEUE_CAPACITY_AVAILABLE")

        if task.required:
            return AdmissionDecision("HOLD_REQUIRED_BACKPRESSURE", score, service, "QUEUE_FULL_REQUIRED_WORK_NOT_DROPPED")
        return AdmissionDecision("REJECT_BACKPRESSURE", score, service, "QUEUE_FULL_OPTIONAL_WORK_REJECTED")


def _wilson_lower(successes: int, trials: int, z: float = 1.96) -> float:
    if trials <= 0 or successes < 0 or successes > trials:
        return 0.0
    p = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    centre = p + z2 / (2.0 * trials)
    margin = z * math.sqrt((p * (1.0 - p) / trials) + z2 / (4.0 * trials * trials))
    return max(0.0, (centre - margin) / denominator)


@dataclass(frozen=True, slots=True)
class GenerationMetrics:
    generation: str
    successes: int
    trials: int
    proof_violations: int
    p95_latency_ms: float
    cost_per_success: float
    owner_burden_per_mission: float

    def validate(self) -> "GenerationMetrics":
        if not self.generation.strip() or self.trials < 0 or self.successes < 0 or self.successes > self.trials:
            raise ValueError("GENERATION_METRICS_INVALID")
        if self.proof_violations < 0:
            raise ValueError("GENERATION_PROOF_VIOLATIONS_INVALID")
        _finite_nonnegative(self.p95_latency_ms, "GENERATION_LATENCY")
        _finite_nonnegative(self.cost_per_success, "GENERATION_COST")
        _finite_nonnegative(self.owner_burden_per_mission, "GENERATION_OWNER_BURDEN")
        return self

    @property
    def success_lower_bound(self) -> float:
        return _wilson_lower(self.successes, self.trials)


@dataclass(frozen=True, slots=True)
class RolloutDecision:
    action: str
    current_share: float
    next_share: float
    candidate_success_lower_bound: float
    champion_success_lower_bound: float
    reason: str


class GenerationRolloutGovernor:
    """Evidence-gated shadow/canary/ramp/rollback policy.

    Inspired by versioned-worker traffic ramping but deliberately provider-neutral.
    It only recommends a share; provider traffic changes remain external effects and
    require their existing authorization/readback path.
    """

    def __init__(
        self,
        *,
        min_trials: int = 30,
        stable_trials: int = 100,
        min_success_lower_bound: float = 0.80,
        success_tolerance: float = 0.02,
        max_latency_regression: float = 0.15,
        max_cost_regression: float = 0.15,
        max_owner_burden_regression: float = 0.0,
        ramp_steps: Sequence[float] = (0.0, 0.05, 0.25, 0.50, 1.0),
    ) -> None:
        if min_trials < 1 or stable_trials < min_trials:
            raise ValueError("ROLLOUT_TRIAL_POLICY_INVALID")
        if not 0.0 <= min_success_lower_bound <= 1.0:
            raise ValueError("ROLLOUT_SUCCESS_FLOOR_INVALID")
        steps = tuple(float(x) for x in ramp_steps)
        if not steps or steps[0] != 0.0 or steps[-1] != 1.0 or any(a >= b for a, b in zip(steps, steps[1:])):
            raise ValueError("ROLLOUT_STEPS_INVALID")
        self.min_trials = int(min_trials)
        self.stable_trials = int(stable_trials)
        self.min_success_lower_bound = float(min_success_lower_bound)
        self.success_tolerance = float(success_tolerance)
        self.max_latency_regression = float(max_latency_regression)
        self.max_cost_regression = float(max_cost_regression)
        self.max_owner_burden_regression = float(max_owner_burden_regression)
        self.ramp_steps = steps

    @staticmethod
    def _regression(candidate: float, champion: float) -> float:
        if champion <= 0:
            return 0.0 if candidate <= champion else float("inf")
        return (candidate - champion) / champion

    def decide(
        self,
        *,
        champion: GenerationMetrics,
        candidate: GenerationMetrics,
        current_share: float,
    ) -> RolloutDecision:
        champion.validate(); candidate.validate()
        current = float(current_share)
        if current not in self.ramp_steps:
            raise ValueError("ROLLOUT_CURRENT_SHARE_NOT_A_STEP")
        clb = candidate.success_lower_bound
        blb = champion.success_lower_bound

        if candidate.proof_violations > 0:
            return RolloutDecision("ROLLBACK", current, 0.0, clb, blb, "PROOF_VIOLATION")
        if candidate.trials < self.min_trials:
            return RolloutDecision("HOLD_SHADOW", current, current, clb, blb, "INSUFFICIENT_CANDIDATE_SAMPLE")
        if clb < self.min_success_lower_bound or clb + self.success_tolerance < blb:
            return RolloutDecision("ROLLBACK" if current > 0 else "REJECT", current, 0.0, clb, blb, "SUCCESS_CONFIDENCE_REGRESSION")

        regressions = (
            self._regression(candidate.p95_latency_ms, champion.p95_latency_ms),
            self._regression(candidate.cost_per_success, champion.cost_per_success),
            self._regression(candidate.owner_burden_per_mission, champion.owner_burden_per_mission),
        )
        limits = (
            self.max_latency_regression,
            self.max_cost_regression,
            self.max_owner_burden_regression,
        )
        if any(value > limit for value, limit in zip(regressions, limits)):
            return RolloutDecision("ROLLBACK" if current > 0 else "REJECT", current, 0.0, clb, blb, "EFFICIENCY_OR_OWNER_BURDEN_REGRESSION")

        if current == 1.0:
            if candidate.trials < self.stable_trials:
                return RolloutDecision("HOLD_FULL_CANARY", current, current, clb, blb, "STABLE_SAMPLE_NOT_REACHED")
            return RolloutDecision("STABLE_CANDIDATE", current, current, clb, blb, "STABLE_EVIDENCE_THRESHOLD_REACHED")

        next_share = self.ramp_steps[self.ramp_steps.index(current) + 1]
        return RolloutDecision("RAMP_CANDIDATE", current, next_share, clb, blb, "ALL_PROMOTION_GATES_PASS")


@dataclass(frozen=True, slots=True)
class MissionGenerationDecision:
    action: str
    generation: str
    reason: str


class MissionGenerationRouter:
    """Pin running missions and upgrade only at explicit checkpoint boundaries."""

    @staticmethod
    def decide(
        *,
        current_generation: str,
        candidate_generation: str,
        checkpoint_boundary: bool,
        candidate_qualified: bool,
        state_compatible: bool,
    ) -> MissionGenerationDecision:
        if not current_generation.strip() or not candidate_generation.strip():
            raise ValueError("MISSION_GENERATION_ID_REQUIRED")
        if current_generation == candidate_generation:
            return MissionGenerationDecision("PIN_CURRENT", current_generation, "ALREADY_ON_REQUESTED_GENERATION")
        if not checkpoint_boundary:
            return MissionGenerationDecision("PIN_CURRENT", current_generation, "MID_EXECUTION_UPGRADE_FORBIDDEN")
        if not candidate_qualified:
            return MissionGenerationDecision("PIN_CURRENT", current_generation, "CANDIDATE_NOT_QUALIFIED")
        if not state_compatible:
            return MissionGenerationDecision("PIN_CURRENT", current_generation, "CHECKPOINT_STATE_INCOMPATIBLE")
        return MissionGenerationDecision("UPGRADE_AT_CHECKPOINT", candidate_generation, "QUALIFIED_COMPATIBLE_BOUNDARY")


@dataclass(frozen=True, slots=True)
class AblationObservation:
    omitted_component: str
    utility: float
    proof_valid: bool
    matched_context_fingerprint: str
    trials: int


@dataclass(frozen=True, slots=True)
class ComponentCredit:
    component: str
    marginal_utility: float
    action: str
    reason: str


class CausalAblationAnalyzer:
    """Matched single-component ablation credit assignment.

    Positive marginal utility means removing the component hurt the mission. Negative
    marginal utility means the matched ablation improved utility. Safety-critical
    components can never be recommended for removal by this analyzer.
    """

    def analyze(
        self,
        *,
        baseline_utility: float,
        baseline_context_fingerprint: str,
        observations: Sequence[AblationObservation],
        safety_critical_components: Sequence[str] = (),
        min_trials: int = 5,
        material_delta: float = 0.02,
    ) -> tuple[ComponentCredit, ...]:
        if not baseline_context_fingerprint.strip() or min_trials < 1 or material_delta < 0:
            raise ValueError("ABLATION_POLICY_INVALID")
        if not math.isfinite(float(baseline_utility)):
            raise ValueError("ABLATION_BASELINE_UTILITY_INVALID")
        safety = {str(x) for x in safety_critical_components}
        output: list[ComponentCredit] = []
        seen: set[str] = set()
        for row in observations:
            component = row.omitted_component.strip()
            if not component or component in seen:
                raise ValueError("ABLATION_COMPONENT_ID_INVALID_OR_DUPLICATE")
            seen.add(component)
            if row.matched_context_fingerprint != baseline_context_fingerprint:
                output.append(ComponentCredit(component, 0.0, "INCONCLUSIVE", "CONTEXT_NOT_MATCHED"))
                continue
            if not row.proof_valid or row.trials < min_trials or not math.isfinite(float(row.utility)):
                output.append(ComponentCredit(component, 0.0, "INCONCLUSIVE", "PROOF_OR_SAMPLE_INSUFFICIENT"))
                continue
            contribution = float(baseline_utility) - float(row.utility)
            if component in safety:
                action = "KEEP_SAFETY_CRITICAL"
                reason = "SAFETY_CRITICAL_COMPONENT_NOT_REMOVABLE_BY_PERFORMANCE_ABLATION"
            elif contribution > material_delta:
                action = "KEEP"
                reason = "MEASURED_POSITIVE_MARGINAL_UTILITY"
            elif contribution < -material_delta:
                action = "REVIEW_REMOVE"
                reason = "MATCHED_ABLATION_OUTPERFORMED_BASELINE"
            else:
                action = "INCONCLUSIVE"
                reason = "MARGINAL_DELTA_BELOW_MATERIALITY"
            output.append(ComponentCredit(component, contribution, action, reason))
        return tuple(output)


@dataclass(frozen=True, slots=True)
class HedgeDecision:
    allow: bool
    reason: str
    runtime_route: str


class ExistingReadHedgeAdmission:
    """Admission policy for the already-admitted SLOS hedge executor.

    This module intentionally does not implement request racing. When allowed, the
    host may call ``superior_logic.parallel_runtime.ParallelLaneExecutor.hedge_read_route``.
    """

    RUNTIME_ROUTE = "superior_logic.parallel_runtime.ParallelLaneExecutor.hedge_read_route"

    def __init__(self, *, trigger_fraction_of_p95: float = 0.90, max_active_hedges: int = 2) -> None:
        if not 0.0 < trigger_fraction_of_p95 <= 1.5 or max_active_hedges < 1:
            raise ValueError("HEDGE_POLICY_INVALID")
        self.trigger_fraction_of_p95 = float(trigger_fraction_of_p95)
        self.max_active_hedges = int(max_active_hedges)

    def decide(
        self,
        *,
        effect_class: str,
        idempotent: bool,
        semantic_readback_available: bool,
        elapsed_ms: float,
        historical_p95_ms: float,
        deadline_remaining_ms: float,
        estimated_secondary_cost: float,
        hedge_budget_remaining: float,
        active_hedges: int,
    ) -> HedgeDecision:
        if effect_class not in {"NO_EFFECT", "READ_ONLY"}:
            return HedgeDecision(False, "EFFECTFUL_HEDGING_FORBIDDEN", self.RUNTIME_ROUTE)
        if not idempotent:
            return HedgeDecision(False, "NON_IDEMPOTENT_HEDGING_FORBIDDEN", self.RUNTIME_ROUTE)
        if not semantic_readback_available:
            return HedgeDecision(False, "SEMANTIC_WINNER_PROOF_UNAVAILABLE", self.RUNTIME_ROUTE)
        values = (elapsed_ms, historical_p95_ms, deadline_remaining_ms, estimated_secondary_cost, hedge_budget_remaining)
        if any(not math.isfinite(float(x)) or float(x) < 0 for x in values) or historical_p95_ms <= 0:
            raise ValueError("HEDGE_OBSERVATION_INVALID")
        if active_hedges < 0 or active_hedges >= self.max_active_hedges:
            return HedgeDecision(False, "HEDGE_CONCURRENCY_BUDGET_EXHAUSTED", self.RUNTIME_ROUTE)
        if estimated_secondary_cost > hedge_budget_remaining:
            return HedgeDecision(False, "HEDGE_COST_BUDGET_EXHAUSTED", self.RUNTIME_ROUTE)
        if elapsed_ms < historical_p95_ms * self.trigger_fraction_of_p95:
            return HedgeDecision(False, "PRIMARY_NOT_YET_TAIL_STRAGGLER", self.RUNTIME_ROUTE)
        if deadline_remaining_ms <= 0:
            return HedgeDecision(False, "NO_DEADLINE_SLACK", self.RUNTIME_ROUTE)
        return HedgeDecision(True, "TAIL_STRAGGLER_READ_HEDGE_ADMITTED", self.RUNTIME_ROUTE)


@dataclass(frozen=True, slots=True)
class FrontierRuntimeV2Receipt:
    schema: str
    capabilities: tuple[str, ...]
    provider_effect_authorized: bool
    traffic_change_authorized: bool
    stable_promotion_authorized: bool


def frontier_runtime_v2_receipt() -> FrontierRuntimeV2Receipt:
    return FrontierRuntimeV2Receipt(
        schema="CHATGOV-FRONTIER-RUNTIME-V2",
        capabilities=(
            "DEPENDENCY_CONTENT_ADDRESSED_REUSE",
            "QUEUE_PRESSURE_BACKPRESSURE_AND_LOAD_SHEDDING",
            "GENERATION_CANARY_RAMP_ROLLBACK_POLICY",
            "CHECKPOINT_ONLY_GENERATION_UPGRADE",
            "MATCHED_CAUSAL_ABLATION_CREDIT",
            "EXISTING_SLOS_READ_HEDGE_ADMISSION",
        ),
        provider_effect_authorized=False,
        traffic_change_authorized=False,
        stable_promotion_authorized=False,
    )


__all__ = [
    "AblationObservation",
    "AdmissionDecision",
    "AdmissionTask",
    "CausalAblationAnalyzer",
    "ComponentCredit",
    "DependencyResultCache",
    "ExistingReadHedgeAdmission",
    "FrontierRuntimeV2Receipt",
    "GenerationMetrics",
    "GenerationRolloutGovernor",
    "HedgeDecision",
    "MissionGenerationDecision",
    "MissionGenerationRouter",
    "ProvenNodeResult",
    "QueuePressureGovernor",
    "RolloutDecision",
    "frontier_runtime_v2_receipt",
]
