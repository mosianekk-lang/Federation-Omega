import asyncio
import unittest

from federation.cfbe_structured_execution_v2 import (
    AsyncReadTask,
    CircuitPolicy,
    CircuitState,
    DynamicCircuitBreaker,
    StructuredReadExecutor,
)


class CFBEConfiguredStructuredExecutionV2Tests(unittest.IsolatedAsyncioTestCase):
    async def test_executor_runs_independent_reads_concurrently(self):
        gate = asyncio.Event()
        started = 0
        lock = asyncio.Lock()

        async def work(label):
            nonlocal started
            async with lock:
                started += 1
                if started >= 2:
                    gate.set()
            await asyncio.wait_for(gate.wait(), timeout=1)
            return label

        tasks = (
            AsyncReadTask("a", "drive", lambda: work("a")),
            AsyncReadTask("b", "github", lambda: work("b")),
        )
        out = await StructuredReadExecutor(global_max_parallel=2).execute(tasks)
        self.assertEqual(out.max_parallel_observed, 2)
        self.assertTrue(all(r.success for r in out.results))

    async def test_executor_respects_surface_bulkhead(self):
        active = 0
        peak = 0
        lock = asyncio.Lock()

        async def work(label):
            nonlocal active, peak
            async with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.02)
            async with lock:
                active -= 1
            return label

        tasks = tuple(
            AsyncReadTask(f"d{i}", "drive", lambda i=i: work(i)) for i in range(3)
        )
        out = await StructuredReadExecutor(
            global_max_parallel=3, surface_limits={"drive": 1}
        ).execute(tasks)
        self.assertEqual(dict(out.surface_peak)["drive"], 1)
        self.assertEqual(peak, 1)

    async def test_executor_captures_failure_without_leaking_task(self):
        async def bad():
            raise RuntimeError("boom")

        async def good():
            await asyncio.sleep(0)
            return "ok"

        out = await StructuredReadExecutor(global_max_parallel=2).execute((
            AsyncReadTask("bad", "drive", bad),
            AsyncReadTask("good", "github", good),
        ))
        states = {r.task_id: r.state for r in out.results}
        self.assertEqual(states["bad"], "FAILED")
        self.assertEqual(states["good"], "SUCCESS")

    async def test_executor_enforces_deadline(self):
        async def slow():
            await asyncio.sleep(0.2)

        out = await StructuredReadExecutor().execute((
            AsyncReadTask("slow", "drive", slow, timeout_seconds=0.01),
        ))
        self.assertEqual(out.results[0].state, "TIMEOUT")

    async def test_executor_rejects_effectful_or_nonidempotent_task(self):
        async def noop():
            return None

        with self.assertRaisesRegex(ValueError, "READ_ONLY_ONLY"):
            await StructuredReadExecutor().execute((
                AsyncReadTask("x", "drive", noop, read_only=False),
            ))
        with self.assertRaisesRegex(ValueError, "IDEMPOTENT_ONLY"):
            await StructuredReadExecutor().execute((
                AsyncReadTask("x", "drive", noop, idempotent=False),
            ))


class CFBEDynamicCircuitV2Tests(unittest.TestCase):
    def policy(self):
        return CircuitPolicy(
            min_samples=4,
            failure_ratio_to_open=0.5,
            open_ticks=2,
            half_open_successes_to_close=2,
        )

    def test_circuit_opens_after_failure_threshold(self):
        c = DynamicCircuitBreaker(self.policy())
        c.record("r", success=True, now_tick=0)
        c.record("r", success=False, now_tick=0)
        c.record("r", success=False, now_tick=0)
        s = c.record("r", success=True, now_tick=0)
        self.assertEqual(s.state, CircuitState.OPEN)
        self.assertFalse(c.allow("r", now_tick=1))

    def test_circuit_transitions_to_half_open_after_cooldown(self):
        c = DynamicCircuitBreaker(self.policy())
        for ok in (False, False, True, True):
            c.record("r", success=ok, now_tick=0)
        self.assertEqual(c.snapshot("r", now_tick=1).state, CircuitState.OPEN)
        self.assertEqual(c.snapshot("r", now_tick=2).state, CircuitState.HALF_OPEN)
        self.assertTrue(c.allow("r", now_tick=2))

    def test_half_open_successes_close_and_reset_window(self):
        c = DynamicCircuitBreaker(self.policy())
        for ok in (False, False, True, True):
            c.record("r", success=ok, now_tick=0)
        c.record("r", success=True, now_tick=2)
        s = c.record("r", success=True, now_tick=2)
        self.assertEqual(s.state, CircuitState.CLOSED)
        self.assertEqual(s.samples, 0)
        self.assertEqual(s.failures, 0)

    def test_half_open_failure_reopens_immediately(self):
        c = DynamicCircuitBreaker(self.policy())
        for ok in (False, False, True, True):
            c.record("r", success=ok, now_tick=0)
        s = c.record("r", success=False, now_tick=2)
        self.assertEqual(s.state, CircuitState.OPEN)
        self.assertEqual(s.opened_at_tick, 2)


if __name__ == "__main__":
    unittest.main()
