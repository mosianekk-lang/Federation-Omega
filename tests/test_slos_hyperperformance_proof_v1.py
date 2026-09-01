from __future__ import annotations

import asyncio
import unittest

from superior_logic.hyperperformance import (
    HyperperformanceError,
    LanePlan,
    ParallelLaneExecutor,
    ParallelPlan,
)
from superior_logic.prove_hyperperformance_v1 import run


class SlosHyperperformanceProofTests(unittest.TestCase):
    def test_reference_proof_receipt(self) -> None:
        receipt = run()
        self.assertEqual(receipt["state"], "DETERMINISTIC_VERIFIED")
        self.assertEqual(receipt["gate_count"], receipt["passed_count"])
        self.assertFalse(receipt["provider_effect_performed"])
        self.assertFalse(receipt["speculative_provider_mutation"])
        self.assertFalse(receipt["stable_release_promoted"])


class ParallelLaneExecutorTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _lane(transition_id: str, *, mutating: bool = False) -> LanePlan:
        return LanePlan(
            lane_id=f"lane:{transition_id}",
            transition_id=transition_id,
            route_ids=(f"route:{transition_id}",),
            priority=1.0,
            critical_path_ms=100.0,
            value_of_information=1.0,
            estimated_latency_ms=100.0,
            estimated_cost=0.0,
            risk=0.0,
            mutating=mutating,
            reversible=True,
            conflict_domains=(f"domain:{transition_id}",),
            execution_mode="NORMAL",
        )

    async def test_execute_plan_really_fans_out_independent_lanes(self) -> None:
        lanes = (self._lane("a"), self._lane("b"))
        plan = ParallelPlan(
            mission_id="m",
            lanes=lanes,
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

        async def runner(lane: LanePlan):
            nonlocal active, peak
            async with lock:
                active += 1
                peak = max(peak, active)
                if active == 2:
                    both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.5)
            async with lock:
                active -= 1
            return {
                "transition_id": lane.transition_id,
                "semantic_verified": True,
                "proof_valid": True,
                "provider_effect_performed": False,
            }

        results = await asyncio.wait_for(
            ParallelLaneExecutor.execute_plan(plan, runner), timeout=1.0
        )
        self.assertEqual(2, peak)
        self.assertEqual({item.transition_id for item in results}, {"a", "b"})

    async def test_read_race_returns_first_semantically_verified_route(self) -> None:
        lane = self._lane("research")

        async def runner(route_id: str):
            await asyncio.sleep(0.01 if route_id == "fast" else 0.05)
            return {
                "route_id": route_id,
                "semantic_verified": True,
                "proof_valid": True,
                "provider_effect_performed": False,
            }

        result = await ParallelLaneExecutor.race_read_routes(
            lane, ("slow", "fast"), runner
        )
        self.assertEqual("fast", result["route_id"])

    async def test_mutation_without_sol_transaction_receipt_is_rejected(self) -> None:
        lane = self._lane("write", mutating=True)
        plan = ParallelPlan(
            mission_id="m",
            lanes=(lane,),
            deferred_transition_ids=(),
            estimated_parallel_latency_ms=100.0,
            estimated_serial_latency_ms=100.0,
            theoretical_speedup=1.0,
            algorithm="CP_VOI_BOUNDED_BEAM_V1",
        )

        async def runner(_lane: LanePlan):
            return {"provider_effect_performed": True}

        with self.assertRaisesRegex(HyperperformanceError, "SOL_TRANSACTION_COMMIT"):
            await ParallelLaneExecutor.execute_plan(plan, runner)

    async def test_mutating_lane_cannot_enter_speculative_route_race(self) -> None:
        lane = self._lane("write", mutating=True)

        async def runner(route_id: str):
            return {"route_id": route_id, "semantic_verified": True, "proof_valid": True}

        with self.assertRaisesRegex(HyperperformanceError, "SPECULATIVE_MUTATION"):
            await ParallelLaneExecutor.race_read_routes(lane, ("a", "b"), runner)


if __name__ == "__main__":
    unittest.main()
