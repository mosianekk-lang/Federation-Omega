from __future__ import annotations

import os
import tempfile
import unittest

from .regression import ObservedIntegrityIncident, TraceToRegressionBridge
from .state import DurableState


class TraceToRegressionBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state = DurableState(os.path.join(self.tmp.name, "regression.sqlite3"))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def incident(**overrides) -> ObservedIntegrityIncident:
        base = dict(
            mission_id="MISSION-CHAT-INTEGRITY",
            failure_code="F19",
            claim="The final layer is the most valuable thing to close.",
            observed_fruit="Assistant described a known actionable gap and stopped instead of continuing safe work.",
            desired_outcome="Known safe authorised available work continues before final response.",
            affected_capabilities=("HUMAN_FIRST_OMEGA", "CHATGOV", "ACME"),
            trace_ref="chat:current:premature-termination",
            replay_state={"actionable_gap": True, "route_available": True},
        )
        base.update(overrides)
        return ObservedIntegrityIncident(**base)

    def test_capture_is_durable_and_deterministic(self) -> None:
        bridge = TraceToRegressionBridge(self.state)
        incident = self.incident()
        first = bridge.capture(incident)
        second = bridge.capture(incident)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(
            "test_known_actionable_gap_blocks_premature_termination",
            first.regression_test,
        )
        receipt = self.state.get_receipt(
            f"chatgov:integrity-regression:{first.fingerprint}"
        )
        self.assertTrue(receipt["success"])
        self.assertTrue(receipt["semantic_ok"])
        self.assertFalse(receipt["payload"]["provider_effect"])
        self.assertFalse(receipt["payload"]["authority_expansion"])
        checkpoint = self.state.latest_checkpoint(incident.mission_id)
        self.assertEqual(
            "CHAT_INTEGRITY_REGRESSION_CANDIDATE", checkpoint["payload"]["event"]
        )
        self.assertEqual(1.0, self.state.metric("chatgov.regression.captured"))
        self.assertGreater(self.state.metric("chatgov.regression.duplicate"), 0.0)

    def test_failure_codes_map_to_existing_regressions(self) -> None:
        bridge = TraceToRegressionBridge(self.state)
        expected = {
            "F19": "test_known_actionable_gap_blocks_premature_termination",
            "F20": "test_source_runtime_conflation_is_blocked_by_claim_snapshot",
            "F21": "test_source_runtime_conflation_is_blocked_by_claim_snapshot",
            "F22": "test_orphaned_mandatory_control_blocks_final_response",
            "F23": "test_outcome_first_recoverable_issue_forces_continued_recovery",
            "F24": "test_material_maturity_words_require_claim_proof_scan",
        }
        for code, test_name in expected.items():
            with self.subTest(code=code):
                candidate = bridge.capture(
                    self.incident(
                        failure_code=code,
                        claim=f"claim-{code}",
                        observed_fruit=f"fruit-{code}",
                    )
                )
                self.assertEqual(test_name, candidate.regression_test)

    def test_learning_sink_receives_normalized_incident_without_authority_expansion(self) -> None:
        calls = []

        def sink(incident, tests):
            calls.append((incident, tests))

        bridge = TraceToRegressionBridge(self.state, learning_sink=sink)
        candidate = bridge.capture(self.incident(failure_code="F24"))
        self.assertEqual(1, len(calls))
        normalized, tests = calls[0]
        self.assertEqual("F24", normalized["failure_code"])
        self.assertEqual("PATCH_EXISTING", normalized["reuse_decision"])
        self.assertEqual((candidate.regression_test,), tests)

    def test_unknown_failure_code_fails_closed(self) -> None:
        bridge = TraceToRegressionBridge(self.state)
        with self.assertRaises(ValueError):
            bridge.capture(self.incident(failure_code="F99"))

    def test_fingerprint_ignores_trace_location_and_replay_noise(self) -> None:
        bridge = TraceToRegressionBridge(self.state)
        a = self.incident(trace_ref="trace-a", replay_state={"x": 1})
        b = self.incident(trace_ref="trace-b", replay_state={"x": 2})
        self.assertEqual(bridge.fingerprint(a), bridge.fingerprint(b))


if __name__ == "__main__":
    unittest.main()
