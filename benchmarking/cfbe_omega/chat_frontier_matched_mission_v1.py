from __future__ import annotations

"""Deterministic matched-mission court for the ChatGov frontier binding.

This is a mechanism-level benchmark, not a production/server latency claim.  The
baseline and candidate receive the same synthetic mission shape.  The baseline
executes every described unit; the candidate is allowed to use only the already-
admitted frontier controls.  The court measures work eliminated without lowering
the proof/effect boundary.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any

from bubbles.chat_governor_omega3.frontier_binding_v1 import FrontierControlPlane
from bubbles.chat_governor_omega3.frontier_extensions_v1 import ContextMessage
from bubbles.chat_governor_omega3.performance_kernel import (
    InformationGainStopRule,
    UnnecessaryWorkMeter,
    WorkMetrics,
)


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class MatchedMissionResult:
    schema: str
    benchmark_kind: str
    baseline_execution_units: int
    candidate_execution_units: int
    execution_unit_reduction_fraction: float
    execution_efficiency_factor: float
    baseline_context_chars: int
    candidate_context_chars: int
    context_reduction_fraction: float
    baseline_tail_release_ms: float
    candidate_tail_release_ms: float
    modeled_tail_release_reduction_fraction: float
    baseline_waste_units: float
    candidate_waste_units: float
    waste_reduction_fraction: float
    two_x_waste_target_met: bool
    proof_quality_non_degraded: bool
    provider_effect_authorized: bool
    production_performance_proven: bool
    provider_native_performance_proven: bool
    result_sha256: str


def run_matched_mission() -> MatchedMissionResult:
    plane = FrontierControlPlane(singleflight_ttl_seconds=60.0)

    # 1) Two identical, verified read requests.  Reference baseline performs both;
    # the frontier candidate safely reuses the first exact result.
    provider_calls: list[str] = []

    def read_once() -> dict[str, Any]:
        provider_calls.append("read")
        return {"value": 7, "semantic_verified": True, "proof_ref": "proof://read/7"}

    first = plane.execute_safe_read(key="same-read", fn=read_once, effect_class="READ_ONLY")
    second = plane.execute_safe_read(key="same-read", fn=read_once, effect_class="READ_ONLY")
    if first != second or len(provider_calls) != 1 or plane.singleflight.reuse_hits != 1:
        raise AssertionError("SAFE_READ_DEDUPLICATION_NOT_PROVEN")

    # 2) Three already-proven successful sibling nodes.  Reference baseline
    # recomputes them; content/dependency identity lets the candidate reuse all 3.
    cache = plane.dependency_cache
    for idx in range(3):
        cache.put(
            node_id=f"node-{idx}",
            input_payload={"input": idx},
            dependency_result_sha256s={},
            code_version="code-v1",
            source_version="source-v1",
            result_ref=f"result://node-{idx}",
            result={"value": idx},
            proof_ref=f"proof://node-{idx}",
        )
    reused_nodes = 0
    for idx in range(3):
        if cache.get(
            node_id=f"node-{idx}",
            input_payload={"input": idx},
            dependency_result_sha256s={},
            code_version="code-v1",
            source_version="source-v1",
        ) is not None:
            reused_nodes += 1
    if reused_nodes != 3 or cache.hits != 3:
        raise AssertionError("INCREMENTAL_REUSE_NOT_PROVEN")

    # 3) Same context corpus.  Baseline forwards all 400 chars; the candidate is
    # constrained to 200 chars while preserving the mandatory proof-bearing item.
    messages = [
        ContextMessage("m1", "mission", "A" * 100, priority=100, mandatory=True, proof_ref="proof://m1"),
        ContextMessage("m2", "mission", "B" * 100, priority=90, proof_ref="proof://m2"),
        ContextMessage("m3", "mission", "C" * 100, priority=20, proof_ref="proof://m3"),
        ContextMessage("m4", "mission", "D" * 100, priority=10, proof_ref="proof://m4"),
    ]
    context_route = plane.context_router.route(
        messages,
        allowed_sources=["mission"],
        max_chars=200,
    )
    if not context_route.selected or context_route.selected[0].message_id != "m1":
        raise AssertionError("MANDATORY_CONTEXT_NOT_PRESERVED")

    # 4) Three equivalent read-only routes.  Baseline ALL waits for the 900 ms
    # straggler; candidate ANY is released by the first semantically valid route.
    join = plane.join_planner.decide(
        workers=["route-fast", "route-mid", "route-slow"],
        completed={"route-fast": True},
        mode="ANY",
    )
    if not join.ready or set(join.cancel_candidates) != {"route-mid", "route-slow"}:
        raise AssertionError("CRITICAL_PATH_JOIN_NOT_PROVEN")
    baseline_tail_ms = 900.0
    candidate_tail_ms = 250.0

    # 5) Two optional low-information investigations.  Candidate applies the
    # existing information-gain rule; baseline performs them unconditionally.
    stop_rule = InformationGainStopRule(threshold=0.25)
    optional_decisions = [
        stop_rule.decide(
            required=False,
            decision_flip_probability=0.10,
            uncertainty_reduction=0.10,
            freshness_gain=0.10,
            acquisition_cost=1.0,
            acquisition_risk=0.1,
            owner_burden=0.1,
        )
        for _ in range(2)
    ]
    candidate_optional = sum(1 for decision in optional_decisions if decision.continue_work)
    if candidate_optional != 0:
        raise AssertionError("LOW_INFORMATION_WORK_NOT_STOPPED")

    # Exact synthetic mission accounting.  These are work/execution units, not ms.
    baseline_execution = 2 + 3 + 3 + 2
    candidate_execution = len(provider_calls) + (3 - reused_nodes) + 1 + candidate_optional
    reduction = 1.0 - (candidate_execution / baseline_execution)
    factor = baseline_execution / candidate_execution

    baseline_context = sum(message.chars for message in messages)
    candidate_context = context_route.total_chars
    context_reduction = 1.0 - candidate_context / baseline_context
    tail_reduction = 1.0 - candidate_tail_ms / baseline_tail_ms

    # Feed the same scenario into the already-admitted waste meter.  This is a
    # second, independently defined accounting view; it is still synthetic.
    baseline_work = WorkMetrics(
        duplicate_reads=1,
        recomputed_successes=3,
        unnecessary_specialists=2,
        repeated_owner_prompts=0,
        tool_round_trips=baseline_execution,
    )
    candidate_work = WorkMetrics(
        duplicate_reads=0,
        recomputed_successes=0,
        unnecessary_specialists=0,
        repeated_owner_prompts=0,
        tool_round_trips=candidate_execution,
    )
    comparison = UnnecessaryWorkMeter.compare(
        baseline=baseline_work,
        candidate=candidate_work,
        baseline_quality=1.0,
        candidate_quality=1.0,
    )

    proof_ok = (
        first["semantic_verified"] is True
        and bool(first["proof_ref"])
        and all(bool(row.proof_ref) for row in cache._entries.values())
        and context_route.selected[0].mandatory
    )

    body = {
        "schema": "CFBE-CHAT-FRONTIER-MATCHED-MISSION-V1",
        "benchmark_kind": "DETERMINISTIC_MECHANISM_LEVEL_MATCHED_MISSION",
        "baseline_execution_units": baseline_execution,
        "candidate_execution_units": candidate_execution,
        "execution_unit_reduction_fraction": round(reduction, 6),
        "execution_efficiency_factor": round(factor, 6),
        "baseline_context_chars": baseline_context,
        "candidate_context_chars": candidate_context,
        "context_reduction_fraction": round(context_reduction, 6),
        "baseline_tail_release_ms": baseline_tail_ms,
        "candidate_tail_release_ms": candidate_tail_ms,
        "modeled_tail_release_reduction_fraction": round(tail_reduction, 6),
        "baseline_waste_units": comparison.baseline_waste_units,
        "candidate_waste_units": comparison.candidate_waste_units,
        "waste_reduction_fraction": round(comparison.reduction_fraction, 6),
        "two_x_waste_target_met": comparison.two_x_target_met,
        "proof_quality_non_degraded": bool(proof_ok and comparison.quality_non_degraded),
        "provider_effect_authorized": False,
        "production_performance_proven": False,
        "provider_native_performance_proven": False,
    }
    return MatchedMissionResult(**body, result_sha256=_digest(body))


if __name__ == "__main__":
    print(json.dumps(asdict(run_matched_mission()), indent=2, sort_keys=True))
