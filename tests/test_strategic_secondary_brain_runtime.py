import unittest

from federation.orchestration.strategic_secondary_brain import (
    ActionDisposition,
    AuthorityClass,
    StrategicHypothesis,
    StrategicOption,
    StrategicSignal,
)
from federation.orchestration.strategic_secondary_brain_runtime import (
    RuntimeCheckpoint,
    RuntimeStatus,
    StrategicEvent,
    StrategicRuntimeKernel,
    provider_runtime_acceptance_contract,
)


def _signal(signal_id="S1"):
    return StrategicSignal(
        signal_id=signal_id,
        source="public-signal",
        observed_at=10,
        summary="A material strategic platform change appeared",
        credibility=.95,
        surprise=.8,
        impact=.95,
        tags=("platform", "agents"),
    )


def _event(event_id="E1", cursor="C1"):
    return StrategicEvent(event_id, cursor, 10, _signal())


def _hypothesis():
    return StrategicHypothesis(
        "H1",
        "The platform change will alter enterprise agent governance demand",
        .7,
        ("No production adoption appears within 180 days",),
        ("S1",),
        180,
    )


def _option(authority=AuthorityClass.A1):
    return StrategicOption(
        "O1",
        "Run a reversible internal challenger benchmark",
        10,
        4,
        3,
        1,
        .1,
        .1,
        .1,
        authority,
        "shadow-benchmark",
        "research-only",
        "semantic FSED readback receipt",
        "discard challenger and preserve evidence",
    )


class StrategicRuntimeKernelTests(unittest.TestCase):
    def setUp(self):
        self.kernel = StrategicRuntimeKernel(cadence_seconds=3600)
        self.cp = RuntimeCheckpoint(source_main="main-a", next_due_at=100)

    def test_no_delta_does_not_manufacture_semantic_execution(self):
        step = self.kernel.step(
            checkpoint=self.cp,
            events=[],
            hypotheses=[],
            options=[],
            source_main="main-a",
            now=50,
        )
        self.assertEqual(step.receipt.status, RuntimeStatus.NO_MATERIAL_DELTA)
        self.assertFalse(step.receipt.semantic_readback_required)
        self.assertIsNone(step.packet)
        self.assertIsNone(step.checkpoint.last_cursor)

    def test_replay_is_idempotently_deduplicated(self):
        first = self.kernel.step(
            checkpoint=self.cp,
            events=[_event()],
            hypotheses=[_hypothesis()],
            options=[_option()],
            source_main="main-a",
            now=50,
        )
        replay = self.kernel.step(
            checkpoint=first.checkpoint,
            events=[_event()],
            hypotheses=[_hypothesis()],
            options=[_option()],
            source_main="main-a",
            now=60,
        )
        self.assertEqual(first.receipt.executed_event_ids, ("E1",))
        self.assertEqual(replay.receipt.executed_event_ids, ())
        self.assertEqual(replay.receipt.deduped_event_ids, ("E1",))
        self.assertFalse(replay.receipt.semantic_readback_required)
        self.assertEqual(replay.checkpoint.last_cursor, "C1")

    def test_a2_action_remains_held(self):
        step = self.kernel.step(
            checkpoint=self.cp,
            events=[_event()],
            hypotheses=[_hypothesis()],
            options=[_option(AuthorityClass.A2)],
            source_main="main-a",
            now=50,
        )
        self.assertEqual(step.receipt.status, RuntimeStatus.HELD_AUTHORITY)
        self.assertEqual(step.receipt.authority, AuthorityClass.A2)
        self.assertEqual(step.packet.disposition, ActionDisposition.HOLD_AUTHORITY)

    def test_failure_checkpoint_does_not_advance_cursor_and_next_run_recovers(self):
        failed = self.kernel.record_failure(self.cp, failure_fingerprint="ERR-1")
        self.assertIsNone(failed.last_cursor)
        self.assertEqual(failed.consecutive_failures, 1)
        recovered = self.kernel.step(
            checkpoint=failed,
            events=[_event()],
            hypotheses=[_hypothesis()],
            options=[_option()],
            source_main="main-a",
            now=50,
        )
        self.assertTrue(recovered.receipt.resumed_after_failure)
        self.assertEqual(recovered.checkpoint.last_cursor, "C1")
        self.assertEqual(recovered.checkpoint.consecutive_failures, 0)
        self.assertIsNone(recovered.checkpoint.last_failure_fingerprint)

    def test_missed_run_recovery_is_explicit(self):
        step = self.kernel.step(
            checkpoint=self.cp,
            events=[_event()],
            hypotheses=[_hypothesis()],
            options=[_option()],
            source_main="main-a",
            now=101,
        )
        self.assertTrue(step.receipt.missed_run_recovered)
        self.assertEqual(step.checkpoint.next_due_at, 3701)

    def test_heartbeat_is_liveness_only(self):
        beat = self.kernel.heartbeat(self.cp, now=20)
        self.assertEqual(beat.heartbeat_seq, self.cp.heartbeat_seq + 1)
        self.assertEqual(beat.last_cursor, self.cp.last_cursor)
        self.assertEqual(beat.last_packet_fingerprint, self.cp.last_packet_fingerprint)

    def test_source_epoch_change_is_recorded_in_checkpoint(self):
        step = self.kernel.step(
            checkpoint=self.cp,
            events=[],
            hypotheses=[],
            options=[],
            source_main="main-b",
            now=50,
        )
        self.assertEqual(step.checkpoint.source_main, "main-b")
        self.assertEqual(step.receipt.source_main, "main-b")

    def test_provider_contract_requires_recovery_and_semantic_readback(self):
        contract = provider_runtime_acceptance_contract()
        required = set(contract["required"])
        self.assertIn("missed_run_recovery", required)
        self.assertIn("crash_resume_without_cursor_advance", required)
        self.assertIn("semantic_execution_receipt", required)
        self.assertIn("post_write_provider_readback", required)
        self.assertIn("a2_exact_authority_hold", required)


if __name__ == "__main__":
    unittest.main()
