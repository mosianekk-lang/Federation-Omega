import threading
import time
import unittest

from bubbles.chat_governor_omega3.frontier_extensions_v1 import (
    CheckpointInterruptLedger,
    ContextMessage,
    ContextMessageRouter,
    CriticalPathJoinPlanner,
    SingleFlightReadCoordinator,
)


class SingleFlightTests(unittest.TestCase):
    def test_duplicate_concurrent_reads_execute_once(self):
        sf = SingleFlightReadCoordinator()
        started = threading.Event()
        release = threading.Event()
        calls = []
        results = []

        def work():
            calls.append("x")
            started.set()
            self.assertTrue(release.wait(2.0))
            return {"value": 7}

        def runner():
            results.append(sf.run("same-read", work))

        t1 = threading.Thread(target=runner)
        t2 = threading.Thread(target=runner)
        t1.start()
        self.assertTrue(started.wait(2.0))
        t2.start()
        time.sleep(0.05)
        release.set()
        t1.join(2.0)
        t2.join(2.0)

        self.assertEqual(1, len(calls))
        self.assertEqual([{"value": 7}, {"value": 7}], results)
        self.assertEqual(1, sf.executions)
        self.assertEqual(1, sf.coalesced_waiters)

    def test_effectful_work_is_never_coalesced(self):
        sf = SingleFlightReadCoordinator()
        with self.assertRaisesRegex(ValueError, "SINGLEFLIGHT_EFFECTFUL_OPERATION_FORBIDDEN"):
            sf.run("write", lambda: None, effect_class="CONSEQUENTIAL_EFFECT")

    def test_bounded_completed_result_reuse(self):
        sf = SingleFlightReadCoordinator(reuse_ttl_seconds=10)
        calls = []
        self.assertEqual(1, sf.run("k", lambda: calls.append(1) or 1))
        self.assertEqual(1, sf.run("k", lambda: calls.append(2) or 2))
        self.assertEqual([1], calls)
        self.assertEqual(1, sf.reuse_hits)


class ContextRouterTests(unittest.TestCase):
    def test_message_graph_is_filtered_separately_from_execution_graph(self):
        router = ContextMessageRouter()
        messages = [
            ContextMessage("m1", "research", "A" * 20, priority=10, mandatory=True, proof_ref="p1"),
            ContextMessage("m2", "legal", "B" * 20, priority=100),
            ContextMessage("m3", "research", "C" * 20, priority=5),
            ContextMessage("m4", "research", "D" * 20, priority=3),
        ]
        route = router.route(messages, allowed_sources=["research"], max_chars=40)
        self.assertEqual(("m1", "m3"), tuple(m.message_id for m in route.selected))
        self.assertEqual(40, route.total_chars)
        self.assertIn("m2", route.omitted_ids)
        self.assertIn("m4", route.omitted_ids)
        self.assertEqual(64, len(route.route_sha256))

    def test_mandatory_context_cannot_be_silently_truncated(self):
        router = ContextMessageRouter()
        with self.assertRaisesRegex(ValueError, "MANDATORY_CONTEXT_EXCEEDS_BUDGET"):
            router.route(
                [ContextMessage("m1", "x", "A" * 21, mandatory=True)],
                allowed_sources=["x"],
                max_chars=20,
            )


class JoinPlannerTests(unittest.TestCase):
    def test_any_join_releases_critical_path_and_marks_stragglers(self):
        planner = CriticalPathJoinPlanner()
        decision = planner.decide(
            workers=["a", "b", "c"],
            completed={"b": True},
            mode="ANY",
        )
        self.assertTrue(decision.ready)
        self.assertEqual(("b",), decision.successful)
        self.assertEqual(("a", "c"), decision.cancel_candidates)

    def test_quorum_waits_until_threshold(self):
        planner = CriticalPathJoinPlanner()
        waiting = planner.decide(
            workers=["a", "b", "c"],
            completed={"a": True, "b": False},
            mode="QUORUM",
            quorum=2,
        )
        self.assertFalse(waiting.ready)
        reached = planner.decide(
            workers=["a", "b", "c"],
            completed={"a": True, "b": False, "c": True},
            mode="QUORUM",
            quorum=2,
        )
        self.assertTrue(reached.ready)


class InterruptLedgerTests(unittest.TestCase):
    def test_exact_checkpoint_resume_and_one_shot_semantics(self):
        ledger = CheckpointInterruptLedger()
        record = ledger.pause(
            mission_id="mission-1",
            checkpoint_ref="cp://1",
            checkpoint_sha256="a" * 64,
            payload={"owner_decision": "choose route"},
        )
        restored = CheckpointInterruptLedger.load(ledger.dump())
        receipt = restored.resume(
            interrupt_id=record.interrupt_id,
            mission_id="mission-1",
            checkpoint_sha256="a" * 64,
            resume_value={"route": "B"},
        )
        self.assertEqual(record.interrupt_id, receipt.interrupt_id)
        self.assertEqual(64, len(receipt.receipt_sha256))
        with self.assertRaisesRegex(ValueError, "INTERRUPT_ALREADY_RESUMED"):
            restored.resume(
                interrupt_id=record.interrupt_id,
                mission_id="mission-1",
                checkpoint_sha256="a" * 64,
                resume_value={"route": "B"},
            )

    def test_checkpoint_mismatch_fails_closed(self):
        ledger = CheckpointInterruptLedger()
        record = ledger.pause(
            mission_id="m",
            checkpoint_ref="cp://x",
            checkpoint_sha256="b" * 64,
            payload={},
        )
        with self.assertRaisesRegex(ValueError, "INTERRUPT_CHECKPOINT_MISMATCH"):
            ledger.resume(
                interrupt_id=record.interrupt_id,
                mission_id="m",
                checkpoint_sha256="c" * 64,
                resume_value="go",
            )


if __name__ == "__main__":
    unittest.main()
