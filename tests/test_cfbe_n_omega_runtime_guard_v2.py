import unittest

from federation.cfbe_chat_hyperperformance_v2 import (
    ActionKind,
    ExecutionState,
    FailureObservation,
    ProgressSnapshot,
)
from federation.cfbe_n_omega_runtime_guard_v2 import (
    NOmegaCFBERuntimeGuardV2,
    RuntimeGuardRequest,
)


class NOmegaCFBERuntimeGuardV2Tests(unittest.TestCase):
    def guard(self):
        return NOmegaCFBERuntimeGuardV2(directive_similarity_threshold=0.75)

    def test_provider_action_is_admitted_when_it_is_the_proposed_action(self):
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.PROVIDER_WRITE,
            execution_state=ExecutionState("m", actionable_provider_steps=("CANVA_EDIT",)),
            previous_progress=ProgressSnapshot(),
            current_progress=ProgressSnapshot(provider_actions=1),
        )
        out = self.guard().evaluate(req)
        self.assertTrue(out.admitted)
        self.assertEqual(out.required_action, "CANVA_EDIT")

    def test_report_is_held_when_provider_action_exists(self):
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.REPORT,
            execution_state=ExecutionState("m", actionable_provider_steps=("CANVA_EDIT",)),
        )
        out = self.guard().evaluate(req)
        self.assertFalse(out.admitted)
        self.assertEqual(out.required_action, "CANVA_EDIT")
        self.assertIn("EXECUTABLE_PROVIDER_WORK_PRECEDES_REPORT", out.reasons)

    def test_duplicate_directive_without_new_evidence_is_held(self):
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.REPORT,
            execution_state=ExecutionState("m"),
            previous_directive="execute Canva edit preview ask approval commit read back",
            proposed_directive="execute Canva edit, preview, ask approval, commit, read back",
        )
        out = self.guard().evaluate(req)
        self.assertFalse(out.admitted)
        self.assertTrue(out.duplicate_directive)
        self.assertEqual(out.required_action, "EXECUTE_OR_EVOLVE_BEFORE_NEXT_DIRECTIVE")

    def test_new_evidence_allows_similar_directive_but_no_progress_report_still_held_when_metrics_flat(self):
        state = ExecutionState("m", new_evidence_refs=("proof:new",))
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.REPORT,
            execution_state=state,
            previous_directive="execute provider readback then continue",
            proposed_directive="execute provider readback and continue",
        )
        out = self.guard().evaluate(req)
        self.assertFalse(out.admitted)
        self.assertNotIn("DUPLICATE_DIRECTIVE_WITHOUT_NEW_EVIDENCE", out.reasons)
        self.assertIn("NO_MONOTONIC_PROGRESS_FOR_NARRATIVE_OUTPUT", out.reasons)

    def test_terminal_report_is_admitted(self):
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.REPORT,
            execution_state=ExecutionState("m", terminal_complete=True),
        )
        out = self.guard().evaluate(req)
        self.assertTrue(out.admitted)
        self.assertEqual(out.required_action, "REPORT_FINAL")

    def test_owner_gate_is_admitted_when_precise(self):
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.OWNER_GATE,
            execution_state=ExecutionState(
                "m", owner_gate_required=True, owner_gate_request="Approve Canva save"
            ),
        )
        out = self.guard().evaluate(req)
        self.assertTrue(out.admitted)
        self.assertEqual(out.required_action, "OWNER_GATE")

    def test_repeated_failure_selects_materially_different_route(self):
        old = FailureObservation("TOOL_SELECTION", "canva", "EDIT", "canva-direct", "MISSING_TOOL", "p1")
        current = FailureObservation("TOOL_SELECTION", "canva", "EDIT", "canva-direct", "MISSING_TOOL", "p2")
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.LOCAL_ANALYSIS,
            execution_state=ExecutionState("m"),
            current_failure=current,
            failure_history=(old,),
            candidate_recovery_routes=("canva-direct", "google-slides-fallback"),
        )
        out = self.guard().evaluate(req)
        self.assertFalse(out.admitted)
        self.assertEqual(out.selected_recovery_route, "google-slides-fallback")
        self.assertEqual(out.required_action, "RECOVERY_ROUTE:google-slides-fallback")

    def test_narrative_output_requires_monotonic_progress(self):
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.REPORT,
            execution_state=ExecutionState("m"),
            previous_progress=ProgressSnapshot(provider_actions=1),
            current_progress=ProgressSnapshot(provider_actions=1),
        )
        out = self.guard().evaluate(req)
        self.assertFalse(out.admitted)
        self.assertIn("NO_MONOTONIC_PROGRESS_FOR_NARRATIVE_OUTPUT", out.reasons)

    def test_progressed_milestone_report_is_admitted(self):
        req = RuntimeGuardRequest(
            mission_id="m",
            proposed_action=ActionKind.REPORT,
            execution_state=ExecutionState("m"),
            previous_progress=ProgressSnapshot(provider_actions=1),
            current_progress=ProgressSnapshot(provider_actions=2),
        )
        out = self.guard().evaluate(req)
        self.assertTrue(out.admitted)
        self.assertTrue(out.monotonic_progress_observed)

    def test_mission_mismatch_fails_closed(self):
        req = RuntimeGuardRequest(
            mission_id="m1",
            proposed_action=ActionKind.LOCAL_ANALYSIS,
            execution_state=ExecutionState("m2"),
        )
        with self.assertRaisesRegex(ValueError, "EXECUTION_STATE_MISSION_MISMATCH"):
            self.guard().evaluate(req)


if __name__ == "__main__":
    unittest.main()
