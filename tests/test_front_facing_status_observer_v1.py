from __future__ import annotations

import unittest

from client_observer.front_facing_status_observer_v1 import (
    FrontFacingSnapshot,
    FrontFacingStatusObserver,
)


def snapshot(
    *,
    t: float,
    status: str = "",
    inflight: bool = False,
    stop: bool = False,
    thinking: bool = False,
    tool: bool = False,
    interrupted: bool = False,
    fingerprint: str = "sha256:local-fnv32-aaaa1111",
    length: int = 100,
    progress: bool = True,
) -> FrontFacingSnapshot:
    return FrontFacingSnapshot(
        source_id="FUSE-EDGE-CHATGPT-FRONT-STATUS",
        observed_monotonic=t,
        page_family="chatgpt-web",
        status_text=status,
        response_inflight=inflight,
        stop_button_visible=stop,
        thinking_visible=thinking,
        tool_activity_visible=tool,
        connection_interrupted=interrupted,
        visible_output_fingerprint=fingerprint,
        visible_output_length=length,
        owner_visible_progress=progress,
    )


class FrontFacingStatusObserverTests(unittest.TestCase):
    def test_connection_interrupted_front_message_triggers_recovery_immediately(self):
        observer = FrontFacingStatusObserver(stall_seconds=60)
        result = observer.ingest(
            snapshot(
                t=1,
                status="Connection interrupted. Waiting for the complete answer",
                inflight=True,
                stop=True,
                interrupted=True,
                progress=False,
            )
        )
        self.assertEqual("FRONT_FACING_ERROR", result.state)
        self.assertIsNotNone(result.failure_event)
        self.assertIsNotNone(result.recovery)
        self.assertTrue(result.auto_continue_intent)
        self.assertEqual(
            "TRIGGER_HYPERCUBE_BOTTLENECK_HARVEST",
            result.recovery["next_automated_action"],
        )

    def test_static_thinking_with_stop_button_promotes_to_stall_without_user_report(self):
        observer = FrontFacingStatusObserver(stall_seconds=60)
        first = observer.ingest(
            snapshot(
                t=0,
                status="Thinking",
                inflight=True,
                stop=True,
                thinking=True,
                progress=True,
            )
        )
        self.assertEqual("FRONT_FACING_RUNNING", first.state)

        second = observer.ingest(
            snapshot(
                t=61,
                status="Thinking",
                inflight=True,
                stop=True,
                thinking=True,
                progress=False,
            )
        )
        self.assertEqual("FRONT_FACING_STALLED", second.state)
        self.assertGreaterEqual(second.no_progress_seconds, 60)
        self.assertTrue(second.owner_visible_progress_required)
        self.assertTrue(second.auto_continue_intent)
        self.assertEqual(
            "SILENT_LONG_RUNNING_EXECUTION",
            second.recovery["failure_class"],
        )

    def test_visible_output_change_resets_stall_clock(self):
        observer = FrontFacingStatusObserver(stall_seconds=60)
        observer.ingest(snapshot(t=0, status="Thinking", inflight=True, stop=True))
        changed = observer.ingest(
            snapshot(
                t=50,
                status="Thinking",
                inflight=True,
                stop=True,
                fingerprint="sha256:local-fnv32-bbbb2222",
                length=150,
            )
        )
        self.assertTrue(changed.output_changed)
        self.assertEqual(0.0, changed.no_progress_seconds)

        later = observer.ingest(
            snapshot(
                t=100,
                status="Thinking",
                inflight=True,
                stop=True,
                fingerprint="sha256:local-fnv32-bbbb2222",
                length=150,
                progress=False,
            )
        )
        self.assertEqual("FRONT_FACING_RUNNING", later.state)
        self.assertLess(later.no_progress_seconds, 60)

    def test_no_raw_conversation_body_is_required_for_stall_detection(self):
        observer = FrontFacingStatusObserver(stall_seconds=10)
        observer.ingest(
            snapshot(
                t=0,
                status="Called tool",
                inflight=True,
                stop=True,
                tool=True,
                fingerprint="sha256:local-fnv32-cccc3333",
                length=0,
            )
        )
        stalled = observer.ingest(
            snapshot(
                t=11,
                status="Called tool",
                inflight=True,
                stop=True,
                tool=True,
                fingerprint="sha256:local-fnv32-cccc3333",
                length=0,
                progress=False,
            )
        )
        event = stalled.failure_event
        self.assertIsNotNone(event)
        rendered = repr(event)
        self.assertNotIn("conversation_body", rendered)
        self.assertNotIn("assistant_message_text", rendered)

    def test_explicit_healthy_non_inflight_state_does_not_trigger_recovery(self):
        observer = FrontFacingStatusObserver(stall_seconds=10)
        result = observer.ingest(
            snapshot(
                t=100,
                status="",
                inflight=False,
                stop=False,
                thinking=False,
                tool=False,
                progress=True,
            )
        )
        self.assertEqual("FRONT_FACING_HEALTHY", result.state)
        self.assertIsNone(result.failure_event)
        self.assertIsNone(result.recovery)


if __name__ == "__main__":
    unittest.main()
