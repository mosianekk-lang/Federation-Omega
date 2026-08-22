#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from durable_runtime import (
    DurableMissionRuntime,
    DurableRuntimeError,
    IdempotencyConflict,
    IntegrityViolation,
    InvalidTransition,
    LeaseConflict,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class DurableRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = FakeClock()
        self.db = Path(self.temp.name) / "runtime.sqlite"
        self.runtime = DurableMissionRuntime(self.db, clock=self.clock)
        self.addCleanup(self.runtime.close)
        self.runtime.create_mission("M1", {"objective": "prove"}, idempotency_key="m1")

    def test_wrong_owner_rejected(self):
        with self.assertRaises(DurableRuntimeError):
            DurableMissionRuntime(Path(self.temp.name) / "bad.sqlite", owner_id="SOVARA")

    def test_create_mission_is_idempotent(self):
        first = self.runtime.create_mission("M1", {"objective": "prove"}, idempotency_key="m1")
        second = self.runtime.create_mission("M1", {"objective": "prove"}, idempotency_key="m1")
        self.assertEqual(first["eventHeadSha256"], second["eventHeadSha256"])

    def test_create_mission_collision_rejected(self):
        with self.assertRaises(IdempotencyConflict):
            self.runtime.create_mission("M1", {"objective": "changed"}, idempotency_key="m1")

    def test_event_idempotency_conflict_rejected(self):
        self.runtime.append_event("M1", "OBSERVED", {"x": 1}, idempotency_key="obs")
        with self.assertRaises(IdempotencyConflict):
            self.runtime.append_event("M1", "OBSERVED", {"x": 2}, idempotency_key="obs")

    def test_event_chain_verifies(self):
        result = self.runtime.verify_event_chain("M1")
        self.assertTrue(result["valid"])
        self.assertEqual(result["eventCount"], 1)

    def test_tampered_event_detected(self):
        connection = sqlite3.connect(self.db)
        connection.execute("UPDATE events SET payload_json='{}' WHERE seq=1")
        connection.commit()
        connection.close()
        with self.assertRaises(IntegrityViolation):
            self.runtime.verify_event_chain("M1")

    def test_lease_fence_increments_after_expiry(self):
        first = self.runtime.acquire_lease("M1", "R", "W1", ttl_seconds=10)
        self.clock.advance(11)
        second = self.runtime.acquire_lease("M1", "R", "W2", ttl_seconds=10)
        self.assertEqual(second.fence, first.fence + 1)

    def test_active_lease_conflict_rejected(self):
        self.runtime.acquire_lease("M1", "R", "W1")
        with self.assertRaises(LeaseConflict):
            self.runtime.acquire_lease("M1", "R", "W2")

    def test_lease_ttl_bounded(self):
        with self.assertRaises(LeaseConflict):
            self.runtime.acquire_lease("M1", "R", "W1", ttl_seconds=121)

    def test_heartbeat_preserves_fence(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1", ttl_seconds=10)
        self.clock.advance(2)
        renewed = self.runtime.heartbeat(lease, ttl_seconds=20)
        self.assertEqual(renewed.fence, lease.fence)
        self.assertNotEqual(renewed.expires_at, lease.expires_at)

    def test_stale_fence_cannot_start_task(self):
        stale = self.runtime.acquire_lease("M1", "R", "W1", ttl_seconds=1)
        self.clock.advance(2)
        self.runtime.acquire_lease("M1", "R", "W2", ttl_seconds=10)
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, idempotency_key="t1")
        with self.assertRaises(LeaseConflict):
            self.runtime.start_task("T1", stale)

    def test_restart_recovers_orphan_and_resumes_with_new_fence(self):
        stale = self.runtime.acquire_lease("M1", "R", "W1", ttl_seconds=1)
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, idempotency_key="t1")
        started = self.runtime.start_task("T1", stale)
        self.assertEqual(started["lease_fence"], stale.fence)
        self.runtime.close()
        self.clock.advance(2)
        self.runtime = DurableMissionRuntime(self.db, clock=self.clock)

        receipt = self.runtime.recover_orphaned_tasks(
            "M1", idempotency_key="recover-1"
        )
        self.assertEqual(receipt["retryWaitCount"], 1)
        self.clock.advance(1)
        fresh = self.runtime.acquire_lease("M1", "R", "W2", ttl_seconds=10)
        resumed = self.runtime.start_task("T1", fresh)
        self.assertEqual(resumed["attempt"], 2)
        self.assertEqual(resumed["lease_fence"], stale.fence + 1)
        with self.assertRaises(LeaseConflict):
            self.runtime.start_task("T1", stale)

    def test_orphan_recovery_receipt_is_idempotent(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1", ttl_seconds=1)
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, idempotency_key="t1")
        self.runtime.start_task("T1", lease)
        self.clock.advance(2)
        first = self.runtime.recover_orphaned_tasks(
            "M1", idempotency_key="recover-1"
        )
        second = self.runtime.recover_orphaned_tasks(
            "M1", idempotency_key="recover-1"
        )
        self.assertEqual(first, second)
        replay = self.runtime.replay("M1")
        self.assertEqual(
            sum(event["type"] == "ORPHANED_TASKS_RECOVERED" for event in replay["events"]),
            1,
        )

    def test_exhausted_orphan_is_dead_lettered(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1", ttl_seconds=1)
        self.runtime.enqueue_task(
            "M1", "T1", {"x": 1}, max_attempts=1, idempotency_key="t1"
        )
        self.runtime.start_task("T1", lease)
        self.clock.advance(2)
        receipt = self.runtime.recover_orphaned_tasks(
            "M1", idempotency_key="recover-1"
        )
        self.assertEqual(receipt["deadLetterCount"], 1)
        self.assertEqual(self.runtime.mission_snapshot("M1")["tasks"][0]["state"], "DEAD_LETTER")

    def test_task_lifecycle(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1")
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, idempotency_key="t1")
        started = self.runtime.start_task("T1", lease)
        self.assertEqual(started["attempt"], 1)
        done = self.runtime.complete_task("T1", {"ok": True}, idempotency_key="done1")
        self.assertEqual(done["state"], "COMPLETED")

    def test_complete_requires_running(self):
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, idempotency_key="t1")
        with self.assertRaises(InvalidTransition):
            self.runtime.complete_task("T1", {"ok": True}, idempotency_key="done1")

    def test_retry_backoff_and_due_task(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1")
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, max_attempts=3, idempotency_key="t1")
        self.runtime.start_task("T1", lease)
        failed = self.runtime.fail_task("T1", "temporary", retryable=True, base_backoff_seconds=3)
        self.assertEqual(failed["state"], "RETRY_WAIT")
        self.assertEqual(self.runtime.due_tasks("M1"), [])
        self.clock.advance(3)
        self.assertEqual([item["task_id"] for item in self.runtime.due_tasks("M1")], ["T1"])

    def test_retry_exhaustion_dead_letters(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1")
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, max_attempts=1, idempotency_key="t1")
        self.runtime.start_task("T1", lease)
        failed = self.runtime.fail_task("T1", "permanent", retryable=True)
        self.assertEqual(failed["state"], "DEAD_LETTER")

    def test_cancellation_stops_new_task_start(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1")
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, idempotency_key="t1")
        snapshot = self.runtime.request_cancel("M1", reason="owner objective changed")
        self.assertTrue(snapshot["cancelRequested"])
        with self.assertRaises(InvalidTransition):
            self.runtime.start_task("T1", lease)

    def test_compensation_runs_reverse_completion_order(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1")
        for number in (1, 2):
            self.runtime.enqueue_task(
                "M1", f"T{number}", {"x": number},
                compensation={"undo": number}, idempotency_key=f"t{number}",
            )
            self.runtime.start_task(f"T{number}", lease)
            self.runtime.complete_task(
                f"T{number}", {"ok": number}, idempotency_key=f"done{number}"
            )
        order = []
        self.runtime.request_cancel("M1", reason="canary")
        self.runtime.compensate(
            "M1", lambda task_id, payload: order.append(task_id) or {"undone": payload["undo"]}
        )
        self.assertEqual(order, ["T2", "T1"])
        self.assertEqual(self.runtime.mission_snapshot("M1")["state"], "COMPENSATED")

    def test_compensation_failure_is_terminal_and_visible(self):
        lease = self.runtime.acquire_lease("M1", "R", "W1")
        self.runtime.enqueue_task(
            "M1", "T1", {"x": 1}, compensation={"undo": 1}, idempotency_key="t1"
        )
        self.runtime.start_task("T1", lease)
        self.runtime.complete_task("T1", {"ok": True}, idempotency_key="done1")
        with self.assertRaises(DurableRuntimeError):
            self.runtime.compensate("M1", lambda *_: (_ for _ in ()).throw(ValueError("no")))
        self.assertEqual(self.runtime.mission_snapshot("M1")["state"], "COMPENSATION_FAILED")

    def test_checkpoint_and_replay(self):
        checkpoint = self.runtime.checkpoint("M1")
        replay = self.runtime.replay("M1")
        self.assertEqual(checkpoint["eventCount"], len(replay["events"]))
        self.assertEqual(replay["contract"], "SOVARA_DURABLE_MISSION_RUNTIME_V1")

    def test_span_stores_hashes_not_raw_content(self):
        span = self.runtime.record_span(
            "M1", "invoke_workflow", kind="INTERNAL", status="OK",
            input_value={"private": "content"}, output_value={"result": "ok"},
        )
        self.assertFalse(span["sensitiveContentCaptured"])
        self.assertNotIn("content", str(span))

    def test_backup_restore_semantic_equality(self):
        backup = Path(self.temp.name) / "backup.sqlite"
        restored = Path(self.temp.name) / "restored.sqlite"
        receipt = self.runtime.backup(backup)
        self.assertEqual(receipt.integrity, "ok")
        DurableMissionRuntime.restore(backup, restored)
        restored_runtime = DurableMissionRuntime(restored, clock=self.clock)
        try:
            self.assertEqual(
                self.runtime.replay("M1")["chain"],
                restored_runtime.replay("M1")["chain"],
            )
        finally:
            restored_runtime.close()

    def test_mission_completion_requires_finished_tasks(self):
        self.runtime.enqueue_task("M1", "T1", {"x": 1}, idempotency_key="t1")
        with self.assertRaises(InvalidTransition):
            self.runtime.complete_mission("M1", {"ok": True}, idempotency_key="m1-done")


if __name__ == "__main__":
    unittest.main()
