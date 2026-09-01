from __future__ import annotations

"""CFBE FIT-008: bounded Omega-One scheduler matched court.

This is a deterministic, no-effect synthetic court. It compares the current
Omega-One AdaptiveConcurrencyController with simple fixed-concurrency policies on
one frozen workload corpus. It may falsify a universal scheduler-advantage claim;
it cannot prove provider performance, production value, or stable promotion.
"""

from collections import deque
from dataclasses import asdict, dataclass
from typing import Iterable

from benchmarking.cfbe_omega.scientific_capability_compiler_v2 import canonical_hash
from omega_one.hyperperformance import AdaptiveConcurrencyController, ConcurrencyPolicy

SCHEMA = "CFBE_FIT008_OMEGA_ONE_SCHEDULER_MATCHED_COURT_V1"
FIXED_LIMITS = (2, 3, 4, 5, 6, 8)
TASK_COUNT = 48


@dataclass(frozen=True, slots=True)
class CapacityProfile:
    profile_id: str
    capacities: tuple[int, ...]

    def validate(self) -> "CapacityProfile":
        if not self.profile_id or not self.capacities or any(x < 1 for x in self.capacities):
            raise ValueError("FIT008_PROFILE_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class SchedulerRun:
    policy_id: str
    profile_id: str
    completion_time_units: float
    retry_work: int
    rounds: int
    completed_tasks: int
    starvation_count: int
    maximum_attempts_per_task: int


@dataclass(frozen=True, slots=True)
class SchedulerCourtReceipt:
    schema: str
    source_head_sha: str
    profile_count: int
    task_count_per_profile: int
    candidate_policy: str
    best_fixed_policy: str
    candidate_completion_time_units: float
    best_fixed_completion_time_units: float
    candidate_retry_work: int
    best_fixed_retry_work: int
    completion_time_ratio: float
    retry_work_delta: int
    verdict: str
    candidate_dominates: bool
    all_tasks_completed: bool
    fairness_guardrail_pass: bool
    provider_effect_authorized: bool
    stable_promotion_allowed: bool
    owner_value_proven: bool
    next_action: str
    truth_boundary: tuple[str, ...]
    receipt_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def frozen_profiles() -> tuple[CapacityProfile, ...]:
    return (
        CapacityProfile("LOW_THEN_HIGH", tuple([2] * 8 + [6] * 32)),
        CapacityProfile("STEADY_HIGH", tuple([6] * 40)),
        CapacityProfile("BURSTY", tuple([2, 2, 6, 6] * 10)),
        CapacityProfile("STEADY_LOW", tuple([2] * 40)),
    )


def _simulate(profile: CapacityProfile, *, adaptive: bool, fixed_limit: int = 4) -> SchedulerRun:
    profile.validate()
    if fixed_limit < 1:
        raise ValueError("FIT008_FIXED_LIMIT_INVALID")
    queue = deque(range(TASK_COUNT))
    attempts = [0] * TASK_COUNT
    completed = set()
    retry_work = 0
    elapsed = 0.0
    rounds = 0
    controller = AdaptiveConcurrencyController(
        ConcurrencyPolicy(
            minimum=1,
            initial=4,
            maximum=8,
            target_latency_ms=150.0,
            decrease_ratio=0.5,
            success_window=2,
            critical_reserve=1,
        )
    )
    while queue and rounds < 500:
        capacity = profile.capacities[min(rounds, len(profile.capacities) - 1)]
        limit = controller.limit if adaptive else fixed_limit
        selected = [queue.popleft() for _ in range(min(limit, len(queue)))]
        for task_id in selected:
            attempts[task_id] += 1
        succeeded = selected[:capacity]
        failed = selected[capacity:]
        completed.update(succeeded)
        queue.extend(failed)
        retry_work += len(failed)
        overload = max(0, len(selected) - capacity)
        latency = 100.0 * (1.0 + 0.5 * overload)
        elapsed += latency
        if adaptive:
            controller.observe(
                latency,
                error=bool(failed),
                queue_saturated=bool(failed),
            )
        rounds += 1
    starvation = TASK_COUNT - len(completed)
    return SchedulerRun(
        policy_id="OMEGA_ONE_ADAPTIVE" if adaptive else f"FIXED_{fixed_limit}",
        profile_id=profile.profile_id,
        completion_time_units=elapsed,
        retry_work=retry_work,
        rounds=rounds,
        completed_tasks=len(completed),
        starvation_count=starvation,
        maximum_attempts_per_task=max(attempts),
    )


def _aggregate(runs: Iterable[SchedulerRun]) -> tuple[float, int, int, int]:
    values = tuple(runs)
    return (
        sum(x.completion_time_units for x in values),
        sum(x.retry_work for x in values),
        sum(x.starvation_count for x in values),
        sum(x.completed_tasks for x in values),
    )


def run_fit008_court(*, source_head_sha: str) -> SchedulerCourtReceipt:
    if len(source_head_sha) != 40 or any(c not in "0123456789abcdef" for c in source_head_sha.lower()):
        raise ValueError("FIT008_SOURCE_SHA_INVALID")
    profiles = frozen_profiles()
    candidate_runs = tuple(_simulate(p, adaptive=True) for p in profiles)
    fixed_runs = {
        limit: tuple(_simulate(p, adaptive=False, fixed_limit=limit) for p in profiles)
        for limit in FIXED_LIMITS
    }
    candidate_time, candidate_retry, candidate_starvation, candidate_completed = _aggregate(candidate_runs)
    fixed_aggregates = {limit: _aggregate(runs) for limit, runs in fixed_runs.items()}
    best_limit = min(FIXED_LIMITS, key=lambda limit: (fixed_aggregates[limit][0], fixed_aggregates[limit][1], limit))
    best_time, best_retry, best_starvation, best_completed = fixed_aggregates[best_limit]

    all_completed = (
        candidate_completed == TASK_COUNT * len(profiles)
        and best_completed == TASK_COUNT * len(profiles)
    )
    fairness_pass = candidate_starvation == 0 and best_starvation == 0
    candidate_dominates = candidate_time <= best_time and candidate_retry <= best_retry
    fixed_dominates = best_time <= candidate_time and best_retry <= candidate_retry
    if not all_completed or not fairness_pass:
        verdict = "HELD_GUARDRAIL_FAILURE"
        next_action = "REPAIR_FAIRNESS_OR_COMPLETION_BEFORE_RETEST"
    elif candidate_dominates and (candidate_time < best_time or candidate_retry < best_retry):
        verdict = "QUALIFIED_BOUNDED_SYNTHETIC_DOMINANCE"
        next_action = "PREREGISTER_BROADER_BLIND_CORPUS_BEFORE_ANY_PROMOTION"
    elif fixed_dominates and (best_time < candidate_time or best_retry < candidate_retry):
        verdict = "HYPOTHESIS_FALSIFIED_ON_FROZEN_CORPUS"
        next_action = "RETAIN_SIMPLE_FIXED_BASELINE_AND_REDESIGN_ADAPTIVE_POLICY"
    else:
        verdict = "TRADEOFF_NON_DOMINANT"
        next_action = "TEST_RETRY_COST_AWARE_OR_WORKLOAD_CONDITIONAL_ROUTING"

    payload = {
        "schema": SCHEMA,
        "source_head_sha": source_head_sha.lower(),
        "profile_count": len(profiles),
        "task_count_per_profile": TASK_COUNT,
        "candidate_policy": "OMEGA_ONE_ADAPTIVE",
        "best_fixed_policy": f"FIXED_{best_limit}",
        "candidate_completion_time_units": candidate_time,
        "best_fixed_completion_time_units": best_time,
        "candidate_retry_work": candidate_retry,
        "best_fixed_retry_work": best_retry,
        "completion_time_ratio": round(candidate_time / best_time, 6),
        "retry_work_delta": candidate_retry - best_retry,
        "verdict": verdict,
        "candidate_dominates": candidate_dominates,
        "all_tasks_completed": all_completed,
        "fairness_guardrail_pass": fairness_pass,
        "provider_effect_authorized": False,
        "stable_promotion_allowed": False,
        "owner_value_proven": False,
        "next_action": next_action,
        "truth_boundary": (
            "DETERMINISTIC_SYNTHETIC_NO_PROVIDER_EFFECT",
            "CURRENT_OMEGA_ONE_V086_SOURCE_ONLY",
            "NO_PRODUCTION_PERFORMANCE_OR_OWNER_VALUE_INHERITANCE",
            "NON_DOMINANT_TRADEOFF_CANNOT_SELF_PROMOTE",
        ),
    }
    return SchedulerCourtReceipt(**payload, receipt_sha256=canonical_hash(payload))


__all__ = ["CapacityProfile", "SchedulerCourtReceipt", "SchedulerRun", "frozen_profiles", "run_fit008_court"]
