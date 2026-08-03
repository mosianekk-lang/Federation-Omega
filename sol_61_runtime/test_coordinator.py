import tempfile
import unittest
from pathlib import Path

from coordinator import DistributedCoordinator


class DistributedCoordinatorTests(unittest.TestCase):
    def test_fencing_locking_fairness_backpressure_and_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plane = DistributedCoordinator(root, queue_high_watermark=3)
            w1 = plane.register_worker("worker-a", capabilities=("build",), affinity=("ws-a",))
            w2 = plane.register_worker("worker-b", capabilities=("build",), affinity=("ws-b",))
            self.assertTrue(plane.elect_leader("worker-a", w1["epoch"], lease_seconds=30, now_epoch=100)["elected"])
            self.assertFalse(plane.elect_leader("worker-b", w2["epoch"], lease_seconds=30, now_epoch=101)["elected"])

            first = plane.acquire_lock("resource-x", "worker-a", w1["epoch"], lease_seconds=10, now_epoch=100)
            self.assertTrue(first["acquired"])
            blocked = plane.acquire_lock("resource-x", "worker-b", w2["epoch"], lease_seconds=10, now_epoch=101)
            self.assertFalse(blocked["acquired"])
            takeover = plane.acquire_lock("resource-x", "worker-b", w2["epoch"], lease_seconds=10, now_epoch=111)
            self.assertTrue(takeover["acquired"])
            self.assertGreater(takeover["lock"]["fencing_token"], first["lock"]["fencing_token"])

            plane.submit_job("job-a1", tenant_id="tenant-a", workstream_id="ws-a", capability="build", priority=90)
            plane.submit_job("job-a2", tenant_id="tenant-a", workstream_id="ws-a", capability="build", priority=80)
            plane.submit_job("job-b1", tenant_id="tenant-b", workstream_id="ws-b", capability="build", priority=10)
            with self.assertRaisesRegex(RuntimeError, "QUEUE_BACKPRESSURE"):
                plane.submit_job("job-c1", tenant_id="tenant-c", workstream_id="ws-c", capability="build")

            dispatched1 = plane.dispatch_next("worker-a", w1["epoch"], now_epoch=101)
            self.assertEqual(dispatched1["job_id"], "job-a1")
            self.assertEqual(dispatched1["assigned_worker"], "worker-a")
            plane.complete_job("job-a1", "worker-a", w1["epoch"], result={"ok": True})

            dispatched2 = plane.dispatch_next("worker-a", w1["epoch"], now_epoch=102)
            self.assertEqual(dispatched2["job_id"], "job-b1")
            self.assertEqual(dispatched2["assigned_worker"], "worker-b")

            restarted_worker = plane.register_worker("worker-b", capabilities=("build",), affinity=("ws-b",))
            self.assertGreater(restarted_worker["epoch"], w2["epoch"])
            with self.assertRaisesRegex(RuntimeError, "FENCED_WORKER"):
                plane.complete_job("job-b1", "worker-b", w2["epoch"], result={"stale": True})

            restored = DistributedCoordinator(root, queue_high_watermark=3)
            self.assertTrue(restored.verify_chain())
            self.assertEqual(restored.state.jobs["job-a1"]["status"], "COMPLETED")
            self.assertEqual(restored.state.jobs["job-b1"]["status"], "RUNNING")
            self.assertEqual(restored.state.workers["worker-b"]["epoch"], restarted_worker["epoch"])


if __name__ == "__main__":
    unittest.main()
