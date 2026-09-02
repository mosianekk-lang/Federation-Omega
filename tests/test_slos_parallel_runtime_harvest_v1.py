from __future__ import annotations

import asyncio
import unittest

from sol_61_runtime.sol_62_frontier_primitives import TokenBucket
from superior_logic.parallel_runtime import (
    ALGORITHM,
    BoundedParallelSelector,
    LaneCandidate,
    LaneEffect,
    ParallelLaneExecutor,
    ParallelRuntimeError,
    compile_runtime_receipt,
)


def candidate(
    lane_id: str,
    *,
    expected_value: float = 1.0,
    uncertainty_reduction: float = 0.0,
    critical_path_ms: float = 0.0,
    latency_ms: float = 100.0,
    cost: float = 0.0,
    risk: float = 0.0,
    conflicts: tuple[str, ...] = (),
    routes: tuple[str, ...] = (),
    effect: LaneEffect = LaneEffect.NO_EFFECT,
) -> LaneCandidate:
    return LaneCandidate(
        lane_id=lane_id,
        transition_id=f"transition:{lane_id}",
        expected_value=expected_value,
        uncertainty_reduction=uncertainty_reduction,
        critical_path_ms=critical_path_ms,
        estimated_latency_ms=latency_ms,
        estimated_cost=cost,
        risk=risk,
        conflict_domains=conflicts,
        route_ids=routes,
        effect_class=effect,
    )


class BoundedParallelSelectorTests(unittest.TestCase):
    def test_bounded_beam_can_beat_greedy_choice_under_conflicts(self) -> None:
        selector = BoundedParallelSelector(max_lanes=2, beam_width=16)
        # A is individually strongest but conflicts with both B and C. B+C is the
        # higher-value compatible set, so a useful bounded beam must preserve it.
        plan = selector.select(
            mission_id="beam-global-choice",
            candidates=(
                candidate("A", expected_value=4.0, conflicts=("x", "y")),
                candidate("B", expected_value=2.5, conflicts=("x",)),
                candidate("C", expected_value=2.5, conflicts=("y",)),
            ),
        )
        self.assertEqual({lane.lane_id for lane in plan.lanes}, {"B", "C"})
        self.assertEqual(plan.deferred_lane_ids, ("A",))
        self.assertEqual(plan.algorithm, ALGORITHM)
        self.assertFalse(plan.provider_effect_authorized)
        self.assertFalse(plan.stable_promotion_authorized)
        self.assertEqual(len(plan.plan_sha256), 64)

    def test_plan_digest_is_deterministic_for_same_payload(self) -> None:
        rows = (
            candidate("one", expected_value=1.3, conflicts=("a",)),
            candidate("two", expected_value=1.1, conflicts=("b",)),
        )
        first = BoundedParallelSelector(max_lanes=2).select(
            mission_id="deterministic", candidates=rows
        )
        second = BoundedParallelSelector(max_lanes=2).select(
            mission_id="deterministic", candidates=rows
        )
        self.assertEqual(first.plan_sha256, second.plan_sha256)
        self.assertEqual(first.lanes, second.lanes)

    def test_existing_sol_token_bucket_bounds_fanout(self) -> None:
        bucket = TokenBucket(capacity=1.0, refill_per_second=0.0, initial_tokens=1.0)
        selector = BoundedParallelSelector(
            max_lanes=4,
            beam_width=16,
            token_bucket=bucket,
        )
        plan = selector.select(
            mission_id="token-bounded",
            candidates=(
                candidate("high", expected_value=3.0, cost=0.0),
                candidate("low", expected_value=1.0, cost=0.0),
            ),
            now_epoch=100.0,
        )
        self.assertEqual(tuple(lane.lane_id for lane in plan.lanes), ("high",))
        self.assertEqual(plan.deferred_lane_ids, ("low",))

    def test_work_stealing_respects_conflict_domains(self) -> None:
        selector = BoundedParallelSelector(max_lanes=3)
        plan = selector.select(
            mission_id="steal",
            candidates=(
                candidate("a", expected_value=3.0, conflicts=("shared",)),
                candidate("b", expected_value=2.0, conflicts=("shared",)),
                candidate("c", expected_value=1.0, conflicts=("independent",)),
            ),
        )
        # Build a queue containing all three, including the deferred conflicting lane.
        all_plans = [
            selector.select(mission_id=f"single-{row.lane_id}", candidates=(row,)).lanes[0]
            for row in (
                candidate("a", expected_value=3.0, conflicts=("shared",)),
                candidate("b", expected_value=2.0, conflicts=("shared",)),
                candidate("c", expected_value=1.0, conflicts=("independent",)),
            )
        ]
        assignments = selector.work_steal(all_plans, ("worker-2", "worker-1", "worker-3"))
        assigned = tuple(item.lane_id for item in assignments.values())
        self.assertIn("a", assigned)
        self.assertIn("c", assigned)
        self.assertNotIn("b", assigned)
        self.assertEqual(len(set(assigned)), len(assigned))
        self.assertTrue(plan.lanes)

    def test_validation_rejects_duplicate_lane_identity(self) -> None:
        selector = BoundedParallelSelector()
        with self.assertRaisesRegex(ValueError, "LANE_IDS_MUST_BE_UNIQUE"):
            selector.select(
                mission_id="dupe",
                candidates=(candidate("same"), candidate("same")),
            )


class ParallelLaneExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_plan_has_real_async_overlap_without_provider_effect(self) -> None:
        selector = BoundedParallelSelector(max_lanes=2)
        plan = selector.select(
            mission_id="async-overlap",
            candidates=(
                candidate("left", expected_value=2.0, conflicts=("left",)),
                candidate("right", expected_value=2.0, conflicts=("right",)),
            ),
        )
        active = 0
        peak = 0
        lock = asyncio.Lock()

        async def runner(lane):
            nonlocal active, peak
            async with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.02)
            async with lock:
                active -= 1
            return {
                "lane": lane.lane_id,
                "provider_effect_performed": False,
                "semantic_verified": True,
                "proof_valid": True,
            }

        results = await ParallelLaneExecutor.execute_plan(plan, runner)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(peak, 2)
        receipt = compile_runtime_receipt(plan, results)
        self.assertFalse(receipt.mutating_lane_executed)
        self.assertFalse(receipt.provider_effect_observed)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.stable_promotion_authorized)
        self.assertEqual(len(receipt.receipt_sha256), 64)

    async def test_mutating_lane_is_held_before_runner_invocation(self) -> None:
        selector = BoundedParallelSelector(max_lanes=1)
        plan = selector.select(
            mission_id="mutation-held",
            candidates=(candidate("mutate", effect=LaneEffect.MUTATING),),
        )
        called = False

        async def runner(_lane):
            nonlocal called
            called = True
            return {"provider_effect_performed": True}

        with self.assertRaisesRegex(
            ParallelRuntimeError,
            "MUTATING_LANE_EXECUTION_HELD_BEFORE_RUNNER",
        ):
            await ParallelLaneExecutor.execute_plan(plan, runner)
        self.assertFalse(called)

    async def test_read_or_no_effect_runner_reporting_mutation_fails_closed(self) -> None:
        selector = BoundedParallelSelector(max_lanes=1)
        plan = selector.select(
            mission_id="reported-mutation",
            candidates=(candidate("read", effect=LaneEffect.READ_ONLY),),
        )

        async def runner(_lane):
            return {"provider_effect_performed": True}

        with self.assertRaisesRegex(
            ParallelRuntimeError,
            "READ_OR_NO_EFFECT_LANE_REPORTED_PROVIDER_MUTATION",
        ):
            await ParallelLaneExecutor.execute_plan(plan, runner)

    async def test_read_race_chooses_first_semantically_verified_proof(self) -> None:
        selector = BoundedParallelSelector(max_lanes=1)
        lane = selector.select(
            mission_id="read-race",
            candidates=(
                candidate(
                    "read",
                    effect=LaneEffect.READ_ONLY,
                    routes=("fast-bad", "slow-good"),
                ),
            ),
        ).lanes[0]

        async def route_runner(route_id: str):
            if route_id == "fast-bad":
                await asyncio.sleep(0.001)
                return {
                    "route_id": route_id,
                    "semantic_verified": False,
                    "proof_valid": True,
                    "provider_effect_performed": False,
                }
            await asyncio.sleep(0.01)
            return {
                "route_id": route_id,
                "semantic_verified": True,
                "proof_valid": True,
                "provider_effect_performed": False,
            }

        winner = await ParallelLaneExecutor.race_read_routes(
            lane,
            lane.route_ids,
            route_runner,
        )
        self.assertEqual(winner["route_id"], "slow-good")

    async def test_mutating_speculative_race_is_forbidden_before_route_runner(self) -> None:
        selector = BoundedParallelSelector(max_lanes=1)
        lane = selector.select(
            mission_id="mutating-race",
            candidates=(
                candidate(
                    "mutating",
                    effect=LaneEffect.MUTATING,
                    routes=("one", "two"),
                ),
            ),
        ).lanes[0]
        calls = 0

        async def route_runner(_route_id: str):
            nonlocal calls
            calls += 1
            return {}

        with self.assertRaisesRegex(
            ParallelRuntimeError,
            "SPECULATIVE_MUTATION_RACE_FORBIDDEN",
        ):
            await ParallelLaneExecutor.race_read_routes(
                lane,
                lane.route_ids,
                route_runner,
            )
        self.assertEqual(calls, 0)

    async def test_hedge_keeps_primary_in_flight_and_does_not_relaunch_it(self) -> None:
        selector = BoundedParallelSelector(max_lanes=1)
        lane = selector.select(
            mission_id="hedge",
            candidates=(
                candidate(
                    "read",
                    effect=LaneEffect.READ_ONLY,
                    routes=("primary", "alternate"),
                ),
            ),
        ).lanes[0]
        calls = {"primary": 0, "alternate": 0}

        async def route_runner(route_id: str):
            calls[route_id] += 1
            if route_id == "primary":
                await asyncio.sleep(0.05)
                return {
                    "route_id": route_id,
                    "semantic_verified": True,
                    "proof_valid": True,
                    "provider_effect_performed": False,
                }
            await asyncio.sleep(0.005)
            return {
                "route_id": route_id,
                "semantic_verified": True,
                "proof_valid": True,
                "provider_effect_performed": False,
            }

        winner = await ParallelLaneExecutor.hedge_read_route(
            lane,
            primary_route_id="primary",
            alternate_route_ids=("alternate",),
            hedge_after_seconds=0.005,
            route_runner=route_runner,
        )
        self.assertEqual(winner["route_id"], "alternate")
        self.assertEqual(calls, {"primary": 1, "alternate": 1})

    async def test_route_failure_does_not_mask_later_verified_winner(self) -> None:
        selector = BoundedParallelSelector(max_lanes=1)
        lane = selector.select(
            mission_id="route-failure-isolation",
            candidates=(
                candidate(
                    "read",
                    effect=LaneEffect.READ_ONLY,
                    routes=("fails", "wins"),
                ),
            ),
        ).lanes[0]

        async def route_runner(route_id: str):
            if route_id == "fails":
                raise RuntimeError("synthetic route failure")
            await asyncio.sleep(0.002)
            return {
                "route_id": route_id,
                "semantic_verified": True,
                "proof_valid": True,
                "provider_effect_performed": False,
            }

        winner = await ParallelLaneExecutor.race_read_routes(
            lane,
            lane.route_ids,
            route_runner,
        )
        self.assertEqual(winner["route_id"], "wins")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
