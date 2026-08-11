import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from worker import DurableWorkerPlane, Job


class WorkerPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.plane = DurableWorkerPlane(self.temp.name)
        self.job = Job(
            job_id="job-001",
            mission_id="mission-001",
            workstream_id="ws-001",
            action_class="evidence.process",
            payload={"document": "fixture"},
            idempotency_key="idem-001",
            max_attempts=2,
            checkpoint_id="cp-001",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_idempotent_enqueue_and_completion(self):
        first = self.plane.enqueue(self.job)
        second = self.plane.enqueue(self.job)
        self.assertEqual(first["job_id"], second["job_id"])
        self.plane.heartbeat("worker-a", ("evidence.process",))
        leased = self.plane.lease("worker-a", "evidence.process", lease_seconds=60)
        self.assertEqual("LEASED", leased["status"])
        receipt = self.plane.complete("job-001", "worker-a", {"status": "ok"})
        replay = DurableWorkerPlane(self.temp.name)
        self.assertTrue(replay.verify_event_chain())
        self.assertEqual(receipt["sha256"], replay.state.results["job-001"]["sha256"])
        self.assertEqual("cp-001", receipt["checkpoint_id"])

    def test_expired_lease_recovery(self):
        self.plane.enqueue(self.job)
        self.plane.lease("worker-a", "evidence.process", lease_seconds=1)
        future = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        recovered = self.plane.recover_expired_leases(future)
        self.assertEqual(["job-001"], recovered)
        self.assertEqual("RETRY_READY", self.plane.state.jobs["job-001"]["status"])
        leased = self.plane.lease("worker-b", "evidence.process")
        self.assertEqual("worker-b", leased["leased_by"])
        self.assertEqual(2, leased["attempts"])

    def test_dead_letter_after_bounded_attempts(self):
        self.plane.enqueue(self.job)
        self.plane.lease("worker-a", "evidence.process")
        self.plane.fail("job-001", "worker-a", "TRANSIENT", "first", backoff_seconds=0)
        self.plane.lease("worker-a", "evidence.process")
        failed = self.plane.fail("job-001", "worker-a", "LOGIC", "second", backoff_seconds=0)
        self.assertEqual("DEAD_LETTER", failed["status"])
        self.assertIn("job-001", self.plane.state.dead_letters)

    def test_stale_worker_detection(self):
        heartbeat = self.plane.heartbeat("worker-a", ("evidence.process",))
        future = (datetime.fromisoformat(heartbeat["observed_at"].replace("Z", "+00:00")) + timedelta(seconds=121)).isoformat().replace("+00:00", "Z")
        self.assertEqual(["worker-a"], self.plane.stale_workers(as_of=future))


if __name__ == "__main__":
    unittest.main()
