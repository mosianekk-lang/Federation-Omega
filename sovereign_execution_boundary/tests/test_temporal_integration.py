"""SDK-level proof: history replay and recovery on a replacement worker."""
from pathlib import Path
import asyncio
import tempfile
import unittest
from uuid import uuid4

try:
    from temporalio.common import WorkflowIDReusePolicy
    from temporalio.exceptions import ApplicationError
    from temporalio.testing import WorkflowEnvironment
    from temporalio.worker import Replayer, Worker
except ImportError:  # optional in the zero-dependency local profile
    WorkflowEnvironment = None

from seb.engine import SovereignEngine
from seb.ledger import JsonlLedger
from seb.models import Budget, MissionIR
from seb.policy import PolicyEngine
from seb.providers import MockProvider
from seb.router import ProviderRouter

if WorkflowEnvironment is not None:
    from seb.temporal import SebMissionWorkflow, SebTemporalActivities, TemporalMissionInput


@unittest.skipIf(WorkflowEnvironment is None, "temporalio test dependency unavailable")
class TemporalIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = await WorkflowEnvironment.start_time_skipping()

    async def asyncTearDown(self):
        await self.env.shutdown()
        self.tmp.cleanup()

    def mission(self, mission_id: str) -> MissionIR:
        return MissionIR(mission_id, "produce verified output", ("r1",), ("accepted=true",),
                         budget=Budget(max_tokens=100))

    def activities(self, provider, hook=None):
        engine = SovereignEngine(JsonlLedger(Path(self.tmp.name) / "events.jsonl"),
                                 PolicyEngine(), ProviderRouter([provider]))
        return SebTemporalActivities(engine, lambda value: value.get("accepted") is True, hook)

    async def test_history_replays_with_real_sdk_replayer(self):
        queue = f"seb-replay-{uuid4()}"
        mission = self.mission("temporal-replay")
        provider = MockProvider("p")
        async with Worker(self.env.client, task_queue=queue, workflows=[SebMissionWorkflow],
                          activities=[self.activities(provider).execute_mission]):
            handle = await self.env.client.start_workflow(
                SebMissionWorkflow.run, TemporalMissionInput.from_mission(mission, "hello", {}),
                id=f"seb-{uuid4()}", task_queue=queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            )
            result = await handle.result()
            history = await handle.fetch_history()
        self.assertEqual(result["state"], "COMPLETED")
        self.assertEqual(provider.calls, 1)
        await Replayer(workflows=[SebMissionWorkflow]).replay_workflow(history)
        self.assertEqual(provider.calls, 1, "replay must not repeat provider I/O")

    async def test_scheduled_activity_is_recovered_by_replacement_worker(self):
        queue = f"seb-recovery-{uuid4()}"
        mission = self.mission("temporal-recovery")
        provider = MockProvider("p")
        # Worker 1 owns workflow orchestration but deliberately has no activity
        # implementation. It records the activity schedule in durable History.
        worker = Worker(self.env.client, task_queue=queue, workflows=[SebMissionWorkflow],
                        activities=[], max_cached_workflows=0)
        await worker.__aenter__()
        handle = await self.env.client.start_workflow(
            SebMissionWorkflow.run, TemporalMissionInput.from_mission(mission, "hello", {}),
            id=f"seb-{uuid4()}", task_queue=queue,
        )
        # Allow its workflow task to complete, then remove that worker process.
        await asyncio.sleep(0.5)
        await worker.__aexit__(None, None, None)

        replacement = self.activities(provider)
        async with Worker(self.env.client, task_queue=queue, workflows=[SebMissionWorkflow],
                          activities=[replacement.execute_mission], max_cached_workflows=0):
            result = await asyncio.wait_for(handle.result(), 20)
        self.assertEqual(result["state"], "COMPLETED")
        self.assertEqual(provider.calls, 1, "failed activity attempt performed no provider I/O")

    async def test_fingerprint_substitution_is_non_retryable(self):
        queue = f"seb-drift-{uuid4()}"
        mission = self.mission("temporal-drift")
        provider = MockProvider("p")
        request = TemporalMissionInput.from_mission(mission, "hello", {})
        request = TemporalMissionInput(request.mission, request.prompt, request.schema, "wrong")
        async with Worker(self.env.client, task_queue=queue, workflows=[SebMissionWorkflow],
                          activities=[self.activities(provider).execute_mission]):
            with self.assertRaises(Exception):
                await self.env.client.execute_workflow(
                    SebMissionWorkflow.run, request, id=f"seb-{uuid4()}", task_queue=queue,
                )
        self.assertEqual(provider.calls, 0)
