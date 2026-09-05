from __future__ import annotations

import unittest

from federation.execution_progress_governor_v1 import (
    ExecutionProgressGovernor,
    StatusUpdateGate,
    canonical_action_fingerprint,
)
from formation_omega.autonomic_fabric import MissionStateVector


class ExecutionProgressGovernorV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.before = MissionStateVector(
            verified_closure=0.2,
            information=0.2,
            safety=0.9,
            recoverability=0.5,
            unlock_leverage=0.2,
        )

    def test_same_state_zero_progress_opens_circuit_after_bounded_budget(self) -> None:
        governor = ExecutionProgressGovernor(same_state_retry_budget=2)
        kwargs = dict(action_name="files.find", arguments={"q": "same"}, state_version="s1")
        self.assertTrue(governor.preflight(**kwargs).allow)
        first = governor.record_attempt(before=self.before, after=self.before, result_summary="no new result", **kwargs)
        self.assertEqual(first.decision, "RETRY_BUDGET_REMAINS")
        self.assertTrue(governor.preflight(**kwargs).allow)
        second = governor.record_attempt(before=self.before, after=self.before, result_summary="no new result", **kwargs)
        self.assertEqual(second.decision, "REQUIRE_ROUTE_MUTATION")
        blocked = governor.preflight(**kwargs)
        self.assertFalse(blocked.allow)
        self.assertEqual(blocked.mode, "ROUTE_MUTATION_REQUIRED")

    def test_new_material_state_reopens_same_action_as_new_fingerprint(self) -> None:
        governor = ExecutionProgressGovernor(same_state_retry_budget=1)
        old = dict(action_name="fetch", arguments={"id": 1}, state_version="old")
        governor.record_attempt(before=self.before, after=self.before, result_summary="timeout", **old)
        self.assertFalse(governor.preflight(**old).allow)
        fresh = governor.preflight(action_name="fetch", arguments={"id": 1}, state_version="new")
        self.assertTrue(fresh.allow)
        self.assertNotEqual(fresh.action_fingerprint, governor.preflight(**old).action_fingerprint)

    def test_measurable_progress_resets_zero_progress_streak(self) -> None:
        governor = ExecutionProgressGovernor(zero_progress_streak_limit=2)
        stalled = dict(action_name="search", arguments={"q": "a"}, state_version="s1")
        governor.record_attempt(before=self.before, after=self.before, result_summary="empty", **stalled)
        progressed = MissionStateVector(
            verified_closure=0.2,
            information=0.4,
            safety=0.9,
            recoverability=0.5,
            unlock_leverage=0.2,
        )
        receipt = governor.record_attempt(
            action_name="search",
            arguments={"q": "b"},
            state_version="s1",
            before=self.before,
            after=progressed,
            result_summary="new evidence",
        )
        self.assertTrue(receipt.progress_accepted)
        self.assertEqual(receipt.global_zero_progress_streak, 0)
        self.assertIn("information", receipt.progress_axes)

    def test_regression_blocks_immediate_repeat(self) -> None:
        governor = ExecutionProgressGovernor(same_state_retry_budget=5)
        regressed = MissionStateVector(
            verified_closure=0.2,
            information=0.2,
            safety=0.7,
            recoverability=0.5,
            unlock_leverage=0.2,
        )
        kwargs = dict(action_name="mutate", arguments={"x": 1}, state_version="s1")
        receipt = governor.record_attempt(before=self.before, after=regressed, result_summary="safety regressed", **kwargs)
        self.assertEqual(receipt.decision, "REJECT_REGRESSION_ROUTE_MUTATION_REQUIRED")
        self.assertFalse(governor.preflight(**kwargs).allow)

    def test_fingerprint_changes_with_arguments_or_state(self) -> None:
        base = canonical_action_fingerprint(action_name="tool", arguments={"a": 1}, state_version="s1")
        arg_changed = canonical_action_fingerprint(action_name="tool", arguments={"a": 2}, state_version="s1")
        state_changed = canonical_action_fingerprint(action_name="tool", arguments={"a": 1}, state_version="s2")
        self.assertNotEqual(base, arg_changed)
        self.assertNotEqual(base, state_changed)

    def test_status_updates_require_material_state_delta(self) -> None:
        gate = StatusUpdateGate()
        self.assertTrue(gate.evaluate(state_digest="d1", update_text="started").allow)
        duplicate_state = gate.evaluate(state_digest="d1", update_text="still working")
        self.assertFalse(duplicate_state.allow)
        self.assertEqual(duplicate_state.mode, "SUPPRESS_ZERO_DELTA_STATUS")
        self.assertTrue(gate.evaluate(state_digest="d2", update_text="new proof arrived").allow)
        self.assertTrue(gate.evaluate(state_digest="d2", update_text="failure", material_event=True).allow)


if __name__ == "__main__":
    unittest.main()
