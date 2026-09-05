from __future__ import annotations

import tempfile
import unittest

from bubbles.chat_governor_omega3.regression import ObservedIntegrityIncident, TraceToRegressionBridge
from bubbles.chat_governor_omega3.state import DurableState


class TraceToRegressionBridgeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        self.state = DurableState(tmp.name)
        self.seen = []
        self.bridge = TraceToRegressionBridge(self.state, learning_sink=lambda payload, tests: self.seen.append((payload, tests)))

    def incident(self, code="F25"):
        return ObservedIntegrityIncident(
            mission_id="m1",
            failure_code=code,
            claim="progress noise surfaced",
            observed_fruit="owner received recoverable diagnostics",
            desired_outcome="recover internally and report verified outcome",
            affected_capabilities=("chatgov", "human_first"),
            trace_ref="trace:1",
            replay_state={"recoverable": True},
        )

    def test_capture_is_durable_and_maps_to_regression(self):
        candidate = self.bridge.capture(self.incident("F25"))
        self.assertFalse(candidate.duplicate)
        self.assertEqual(candidate.regression_test, "test_owner_attention_suppresses_recoverable_progress_noise")
        self.assertTrue(candidate.checkpoint_id.startswith("cp_"))
        self.assertEqual(len(self.seen), 1)

    def test_duplicate_incident_is_detected(self):
        first = self.bridge.capture(self.incident("F26"))
        second = self.bridge.capture(self.incident("F26"))
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertTrue(second.duplicate)

    def test_unknown_failure_code_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported chat-integrity failure code"):
            self.bridge.capture(self.incident("F99"))

    def test_current_frontier_failures_have_named_regressions(self):
        expected = {
            "F25": "test_owner_attention_suppresses_recoverable_progress_noise",
            "F26": "test_raw_side_task_payload_cannot_reenter_parent_context",
            "F27": "test_verified_activity_result_replays_without_provider_reexecution",
        }
        for code, test_name in expected.items():
            self.assertEqual(self.bridge.capture(self.incident(code)).regression_test, test_name)


if __name__ == "__main__":
    unittest.main()
