from __future__ import annotations

import unittest

from evidenceops.build_system.aaa_chat_resilience import evaluate_failure_with_aaa
from evidenceops.build_system.chat_failure_resilience import evaluate_failure


class HypercubeChatRecoveryTests(unittest.TestCase):
    def test_silent_long_running_execution_triggers_hypercube_and_continuation(self):
        receipt = evaluate_failure(
            {
                "event_id": "chat-stall-001",
                "message": "Response has stopped changing; still generating",
                "no_progress_seconds": 1800,
                "response_inflight": True,
                "stop_button_visible": True,
                "owner_visible_progress": False,
                "next_pending_action": "continue active mission",
                "affected_missions": 2,
            }
        )
        self.assertEqual("SILENT_LONG_RUNNING_EXECUTION", receipt.failure_class)
        self.assertTrue(receipt.must_continue)
        self.assertEqual(
            "TRIGGER_HYPERCUBE_BOTTLENECK_HARVEST",
            receipt.next_automated_action,
        )
        self.assertTrue(receipt.checkpoint["hypercube_improvement_triggered"])
        self.assertTrue(receipt.checkpoint["auto_continue_intent"])
        self.assertEqual(
            "RESOLUTION_READY",
            receipt.checkpoint["hypercube_resolution"]["action_state"],
        )
        self.assertTrue(receipt.checkpoint["hypercube_resolution"]["portfolio"])

    def test_incomplete_progress_reporting_is_not_a_stop_condition(self):
        receipt = evaluate_failure(
            {
                "event_id": "chat-incomplete-001",
                "message": "Progress not shown while open work remains",
                "incomplete_reporting": True,
                "reporting_open_work": True,
                "mission_complete": False,
                "owner_visible_progress": False,
                "next_pending_action": "continue",
            }
        )
        self.assertEqual("INCOMPLETE_PROGRESS_REPORTING", receipt.failure_class)
        self.assertTrue(receipt.must_continue)
        self.assertTrue(receipt.checkpoint["hypercube_improvement_triggered"])
        actions = {step.action for step in receipt.recovery_steps}
        self.assertIn("CONTINUE_UNAFFECTED_MISSION_LANES", actions)
        self.assertIn("COMPILE_MATERIALLY_DIFFERENT_ROUTE", actions)
        self.assertIn("EMIT_MINIMAL_OWNER_VISIBLE_PROGRESS", actions)

    def test_aaa_suppresses_unchanged_route_while_hypercube_remains_first_action(self):
        receipt = evaluate_failure_with_aaa(
            {
                "message": "Connection interrupted",
                "objective": "continue mission",
                "route_id": "same-route",
                "route_fingerprint": "same-fingerprint",
                "precondition_fingerprint": "same-precondition",
                "route_history": [
                    {
                        "route_id": "prior",
                        "objective": "continue mission",
                        "route_fingerprint": "same-fingerprint",
                        "precondition_fingerprint": "same-precondition",
                        "outcome": "FAILURE",
                        "attempted_at": "2026-09-18T17:00:00+00:00",
                    }
                ],
            }
        )
        effective = receipt["effective_recovery"]
        self.assertEqual(
            "TRIGGER_HYPERCUBE_BOTTLENECK_HARVEST",
            effective["next_automated_action"],
        )
        self.assertTrue(effective["checkpoint"]["aaa_distinct_route_required"])
        self.assertTrue(effective["checkpoint"]["hypercube_improvement_triggered"])
        actions = {step["action"] for step in effective["recovery_steps"]}
        self.assertIn("SUPPRESS_UNCHANGED_FAILED_ROUTE", actions)
        self.assertIn("DISCOVER_MATERIALLY_DIFFERENT_ROUTE", actions)

    def test_explicit_owner_stop_overrides_hypercube_auto_continue(self):
        receipt = evaluate_failure(
            {
                "message": "user cancelled",
                "user_stop": True,
                "no_progress_seconds": 1800,
                "response_inflight": True,
                "stop_button_visible": True,
                "owner_visible_progress": False,
            }
        )
        self.assertEqual("USER_INTERRUPTION", receipt.failure_class)
        self.assertFalse(receipt.must_continue)
        self.assertFalse(receipt.checkpoint["hypercube_improvement_triggered"])
        self.assertEqual("WAIT_FOR_USER_RESUME", receipt.next_automated_action)


if __name__ == "__main__":
    unittest.main()
