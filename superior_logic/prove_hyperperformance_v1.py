from __future__ import annotations

import asyncio
import json

from .capability_graph import CapabilityGraph, CapabilityNode
from .convergence import ConstitutionalConvergence
from .digital_twin import CounterfactualController, FederationDigitalTwin, Intervention
from .execution_fabric import HyperperformanceExecutionFabric
from .hyperperformance import LanePlan, ParallelLaneExecutor, ParallelPlan, ParallelLaneScheduler
from .mission_ir import MissionIRCompiler
from .shadow_evolution import OpportunityScanner, OutcomeSample, ShadowEvolutionLab


async def _prove_actual_parallelism() -> dict[str, bool]:
    lane_a = LanePlan(
        lane_id="lane:a",
        transition_id="a",
        route_ids=("route:a",),
        priority=1.0,
        critical_path_ms=100.0,
        value_of_information=1.0,
        estimated_latency_ms=100.0,
        estimated_cost=0.0,
        risk=0.0,
        mutating=False,
        reversible=True,
        conflict_domains=("domain:a",),
        execution_mode="NORMAL",
    )
    lane_b = LanePlan(
        lane_id="lane:b",
        transition_id="b",
        route_ids=("route:b",),
        priority=1.0,
        critical_path_ms=100.0,
        value_of_information=1.0,
        estimated_latency_ms=100.0,
        estimated_cost=0.0,
        risk=0.0,
        mutating=False,
        reversible=True,
        conflict_domains=("domain:b",),
        execution_mode="NORMAL",
    )
    plan = ParallelPlan(
        mission_id="parallel-proof",
        lanes=(lane_a, lane_b),
        deferred_transition_ids=(),
        estimated_parallel_latency_ms=100.0,
        estimated_serial_latency_ms=200.0,
        theoretical_speedup=2.0,
        algorithm="CP_VOI_BOUNDED_BEAM_V1",
    )
    active = 0
    peak = 0
    both_started = asyncio.Event()
    lock = asyncio.Lock()

    async def lane_runner(lane: LanePlan):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
            if active == 2:
                both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.5)
        await asyncio.sleep(0)
        async with lock:
            active -= 1
        return {
            "route_id": lane.route_ids[0],
            "semantic_verified": True,
            "proof_valid": True,
            "provider_effect_performed": False,
        }

    results = await asyncio.wait_for(
        ParallelLaneExecutor.execute_plan(plan, lane_runner), timeout=1.0
    )

    race_lane = LanePlan(
        lane_id="lane:race",
        transition_id="race",
        route_ids=("slow", "fast"),
        priority=1.0,
        critical_path_ms=100.0,
        value_of_information=1.0,
        estimated_latency_ms=100.0,
        estimated_cost=0.0,
        risk=0.0,
        mutating=False,
        reversible=True,
        conflict_domains=(),
        execution_mode="SPECULATIVE_READ_RACE",
    )

    async def route_runner(route_id: str):
        await asyncio.sleep(0.005 if route_id == "fast" else 0.05)
        return {
            "route_id": route_id,
            "semantic_verified": True,
            "proof_valid": True,
            "provider_effect_performed": False,
        }

    winner = await ParallelLaneExecutor.race_read_routes(
        race_lane, ("slow", "fast"), route_runner
    )
    return {
        "actual_parallel_fanout": peak == 2 and len(results) == 2,
        "semantic_race_fanin": winner.get("route_id") == "fast",
    }


def run() -> dict:
    gates: dict[str, bool] = {}
    convergence = ConstitutionalConvergence()
    contract = convergence.compile_mission(
        mission_id="hyper-proof",
        objective="prove safe high-performance parallelism",
        source_version="proof-source",
        initial_state={"verified": False},
        target_state={"verified": True},
    )
    graph = CapabilityGraph(
        (
            CapabilityNode(
                capability_id="proof-search-a",
                capability="SEARCH",
                operation="SEARCH",
                provider="LOCAL",
                surface="INDEX_A",
                success_rate=0.99,
                proof_quality=0.98,
                latency_ms=200,
                concurrency_limit=8,
            ),
            CapabilityNode(
                capability_id="proof-search-b",
                capability="SEARCH",
                operation="SEARCH",
                provider="LOCAL",
                surface="INDEX_B",
                success_rate=0.97,
                proof_quality=0.98,
                latency_ms=250,
                concurrency_limit=8,
            ),
            CapabilityNode(
                capability_id="proof-verify",
                capability="VERIFY",
                operation="VERIFY",
                provider="LOCAL",
                surface="PROOFOS",
                success_rate=1.0,
                proof_quality=1.0,
                latency_ms=250,
                concurrency_limit=8,
            ),
        )
    )
    mission = MissionIRCompiler().compile(
        contract,
        (
            {
                "transition_id": "research",
                "description": "read-only evidence discovery",
                "required_capabilities": ("SEARCH",),
                "expected_value": 1.0,
                "uncertainty_reduction": 0.9,
                "estimated_latency_ms": 900,
                "speculative_allowed": True,
            },
            {
                "transition_id": "verify",
                "description": "independent verification",
                "required_capabilities": ("VERIFY",),
                "expected_value": 1.0,
                "uncertainty_reduction": 0.7,
                "estimated_latency_ms": 850,
            },
            {
                "transition_id": "close",
                "description": "mission close",
                "dependencies": ("research", "verify"),
                "required_capabilities": ("VERIFY",),
                "expected_value": 1.0,
            },
        ),
    )
    gates["mission_ir_compiled"] = len(mission.compiled_sha256) == 64 and mission.topological_order()[-1] == "close"

    plan = ParallelLaneScheduler(max_lanes=4, beam_width=16).plan(mission, graph, now_epoch=100)
    gates["parallel_critical_path"] = (
        {item.transition_id for item in plan.lanes} == {"research", "verify"}
        and plan.theoretical_speedup > 1.0
    )
    research = next(item for item in plan.lanes if item.transition_id == "research")
    gates["speculation_read_only"] = research.execution_mode == "SPECULATIVE_READ_RACE" and not research.mutating

    gates.update(asyncio.run(_prove_actual_parallelism()))

    twin = FederationDigitalTwin()
    twin.project_mission(mission)
    counterfactuals = CounterfactualController(twin).rank(
        mission,
        (
            Intervention(
                intervention_id="verify-target",
                description="simulate verified target",
                state_patch={"mission:hyper-proof": {"verified": True}},
                expected_value=1.0,
                uncertainty_reduction=0.5,
                risk=0.1,
                cost=0.1,
                latency_ms=100,
                provider_effect_required=True,
            ),
        ),
    )
    gates["digital_twin_counterfactual"] = (
        counterfactuals[0].intervention_id == "verify-target"
        and counterfactuals[0].target_match_ratio == 1.0
        and all(item.provider_effect_performed is False for item in counterfactuals)
    )

    lab = ShadowEvolutionLab()
    for index in range(5):
        lab.record(OutcomeSample("champion", 0.70, 0.80, 2000, 1.0, 1.0, independent_source=f"c{index%2}"))
    for index in range(30):
        lab.record(OutcomeSample("challenger", 0.95, 0.95, 400, 0.2, 0.0, independent_source=f"s{index%2}"))
    promotion = lab.evaluate(champion_id="champion", challenger_id="challenger", min_samples=30)
    gates["empirical_shadow_promotion"] = promotion.promote and promotion.relative_gain > 0.05

    opportunities = OpportunityScanner().scan(
        (
            {"latency_ms": 6000, "owner_interventions": 1, "status": "OK", "operation_signature": "read:x"},
            {"latency_ms": 7000, "owner_interventions": 0, "status": "TIMEOUT", "operation_signature": "read:x"},
            {"latency_ms": 100, "owner_interventions": 1, "status": "OK", "operation_signature": "read:x"},
        )
    )
    gates["automatic_opportunity_discovery"] = any(
        item.opportunity_id == "OPP-MEMOIZE-REPEAT" for item in opportunities
    )

    fabric = HyperperformanceExecutionFabric(graph)
    fabric_receipt = fabric.compile_and_plan(
        contract,
        ({"transition_id": "inspect", "description": "inspect", "expected_value": 1.0},),
        now_epoch=100,
    )
    architecture = fabric.architecture_receipt()
    gates["single_constitutional_fabric"] = (
        architecture["mission_semantic_owner"] == "SLOS"
        and architecture["transaction_kernel_owner"] == "SOL_6_2_KERNEL"
        and architecture["provider_effect_owner"] == "SOVARA"
        and architecture["speculative_provider_mutation"] is False
        and fabric_receipt.provider_effect_performed is False
    )

    passed = all(gates.values())
    receipt = {
        "schema": "SLOS_HYPERPERFORMANCE_PROOF_V1",
        "state": "DETERMINISTIC_VERIFIED" if passed else "FAILED",
        "algorithm": "MISSION_IR_CP_VOI_BOUNDED_BEAM_DIGITAL_TWIN_SHADOW_EVOLUTION_V1",
        "gates": gates,
        "gate_count": len(gates),
        "passed_count": sum(1 for value in gates.values() if value),
        "provider_effect_performed": False,
        "speculative_provider_mutation": False,
        "stable_release_promoted": False,
    }
    if not passed:
        raise AssertionError(json.dumps(receipt, sort_keys=True))
    return receipt


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
