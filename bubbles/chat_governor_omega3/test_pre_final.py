from __future__ import annotations

import os
import tempfile
import unittest

from .pre_final import (
    ChatGovPreFinalInterlock,
    ClaimScanSnapshot,
    ControlBinding,
    GapState,
    MissionClosureState,
    PreFinalGate,
    TerminalState,
)
from .state import DurableState


class PreFinalGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = PreFinalGate()

    @staticmethod
    def mission(**overrides) -> MissionClosureState:
        base = dict(mission_id="MISSION-TEST", objective="Finish the actual mission")
        base.update(overrides)
        return MissionClosureState(**base)

    def test_known_actionable_gap_blocks_premature_termination(self) -> None:
        decision = self.gate.evaluate(
            mission=self.mission(
                gaps=(
                    GapState(
                        "RUNTIME-BINDING",
                        "Known runtime binding remains",
                        route_known=True,
                        safe=True,
                        authorized=True,
                        available=True,
                    ),
                )
            )
        )
        self.assertFalse(decision.allow_final)
        self.assertTrue(decision.continue_work)
        self.assertIn(
            "KNOWN_ACTIONABLE_GAP_REMAINS:RUNTIME-BINDING", decision.reasons
        )

    def test_verified_complete_allows_final_only_when_objective_satisfied(self) -> None:
        allowed = self.gate.evaluate(
            mission=self.mission(
                terminal_state=TerminalState.VERIFIED_COMPLETE,
                objective_satisfied=True,
            )
        )
        self.assertTrue(allowed.allow_final)
        self.assertEqual("ALLOW_VERIFIED_COMPLETE", allowed.mode)

        blocked = self.gate.evaluate(
            mission=self.mission(terminal_state=TerminalState.VERIFIED_COMPLETE)
        )
        self.assertFalse(blocked.allow_final)
        self.assertIn(
            "VERIFIED_COMPLETE_WITHOUT_OBJECTIVE_SATISFACTION", blocked.reasons
        )

    def test_owner_decision_must_be_precise(self) -> None:
        blocked = self.gate.evaluate(
            mission=self.mission(terminal_state=TerminalState.OWNER_DECISION_REQUIRED)
        )
        self.assertFalse(blocked.allow_final)
        self.assertIn("OWNER_DECISION_REQUEST_NOT_PRECISE", blocked.reasons)

        allowed = self.gate.evaluate(
            mission=self.mission(
                terminal_state=TerminalState.OWNER_DECISION_REQUIRED,
                owner_decision_request="Choose whether to authorize the irreversible filing.",
            )
        )
        self.assertTrue(allowed.allow_final)
        self.assertTrue(allowed.human_required)
        self.assertEqual("ALLOW_PRECISE_OWNER_DECISION", allowed.mode)

    def test_active_turn_boundary_requires_checkpoint_and_no_executable_work(self) -> None:
        blocked = self.gate.evaluate(
            mission=self.mission(
                terminal_state=TerminalState.ACTIVE_TURN_BOUNDARY,
                resumable_checkpoint_ref="cp-1",
                currently_executable_work=True,
            )
        )
        self.assertFalse(blocked.allow_final)
        self.assertIn("ACTIVE_TURN_BOUNDARY_HAS_EXECUTABLE_WORK", blocked.reasons)

        allowed = self.gate.evaluate(
            mission=self.mission(
                terminal_state=TerminalState.ACTIVE_TURN_BOUNDARY,
                resumable_checkpoint_ref="cp-1",
                currently_executable_work=False,
            )
        )
        self.assertTrue(allowed.allow_final)

    def test_material_maturity_words_require_claim_proof_scan(self) -> None:
        decision = self.gate.evaluate(
            mission=self.mission(),
            candidate_response="Human-First is fully implemented and operational.",
        )
        self.assertFalse(decision.allow_final)
        self.assertTrue(decision.rewrite_required)
        self.assertIn("MATERIAL_MATURITY_CLAIM_SCAN_REQUIRED", decision.reasons)

    def test_source_runtime_conflation_is_blocked_by_claim_snapshot(self) -> None:
        scan = ClaimScanSnapshot(
            subject="Human-First runtime",
            verdict="BLOCK_COMPLETION",
            claimed_state="RUNNING",
            proven_state="TESTED",
            state_gap=6,
            safe_statement="Human-First: evidence currently supports TESTED, not RUNNING.",
            evidence_refs=("ci:123",),
        )
        decision = self.gate.evaluate(
            mission=self.mission(),
            candidate_response="Human-First is operational.",
            claim_scans=(scan,),
        )
        self.assertFalse(decision.allow_final)
        self.assertTrue(decision.rewrite_required)
        self.assertIn("CLAIM_PROOF_GATE_BLOCK:Human-First runtime", decision.reasons)
        self.assertIn(scan.safe_statement, decision.safe_statements)

    def test_realityguard_rewrite_verdict_blocks_emission_until_rewritten(self) -> None:
        decision = self.gate.evaluate(
            mission=self.mission(),
            candidate_response="The system is active.",
            claim_scans=(
                {
                    "subject": "system",
                    "verdict": "REWRITE_REQUIRED",
                    "claimed_state": "RUNNING",
                    "proven_state": "BOUND",
                    "state_gap": 0,
                    "safe_statement": "System is source-bound; runtime is not asserted.",
                },
            ),
        )
        self.assertFalse(decision.allow_final)
        self.assertTrue(decision.rewrite_required)
        self.assertIn("CLAIM_REWRITE_REQUIRED:system", decision.reasons)

    def test_orphaned_mandatory_control_blocks_final_response(self) -> None:
        control = ControlBinding(
            control_id="SOLVE_BEFORE_REPORT",
            mandatory=True,
            required_points=("PRE_USER_PROMPT", "PRE_FINAL_RESPONSE"),
            bound_points=("PRE_USER_PROMPT",),
            regression_test_passed=True,
        )
        decision = self.gate.evaluate(mission=self.mission(), controls=(control,))
        self.assertFalse(decision.allow_final)
        self.assertIn("MANDATORY_CONTROL_ORPHANED_OR_UNTESTED", decision.reasons)
        self.assertIn(
            "SOLVE_BEFORE_REPORT:PRE_FINAL_RESPONSE",
            decision.missing_control_bindings,
        )

    def test_control_without_regression_proof_is_not_treated_as_enforced(self) -> None:
        control = ControlBinding(
            control_id="CLAIM_INTEGRITY",
            mandatory=True,
            required_points=("PRE_FINAL_RESPONSE",),
            bound_points=("PRE_FINAL_RESPONSE",),
            regression_test_passed=False,
        )
        decision = self.gate.evaluate(mission=self.mission(), controls=(control,))
        self.assertFalse(decision.allow_final)
        self.assertIn("CLAIM_INTEGRITY:REGRESSION_UNPROVEN", decision.missing_control_bindings)

    def test_healthy_control_does_not_create_a_false_terminal_state(self) -> None:
        control = ControlBinding(
            control_id="CLAIM_INTEGRITY",
            mandatory=True,
            required_points=("PRE_FINAL_RESPONSE",),
            bound_points=("PRE_FINAL_RESPONSE",),
            regression_test_passed=True,
        )
        decision = self.gate.evaluate(mission=self.mission(), controls=(control,))
        self.assertFalse(decision.allow_final)
        self.assertIn("MISSION_ACTIVE_NO_VALID_TERMINAL_STATE", decision.reasons)

    def test_outcome_first_recoverable_issue_forces_continued_recovery(self) -> None:
        decision = self.gate.evaluate(
            mission=self.mission(outcome_first_continue_recovery=True)
        )
        self.assertFalse(decision.allow_final)
        self.assertTrue(decision.continue_work)
        self.assertIn(
            "RECOVERABLE_ISSUE_REQUIRES_CONTINUED_RECOVERY", decision.reasons
        )

    def test_irreducible_blocker_requires_exhaustion_evidence(self) -> None:
        blocked = self.gate.evaluate(
            mission=self.mission(
                terminal_state=TerminalState.BLOCKED_IRREDUCIBLY,
                irreducible_blocker="Provider does not expose the required operation.",
            )
        )
        self.assertFalse(blocked.allow_final)
        self.assertIn("IRREDUCIBLE_BLOCK_NOT_PROVEN", blocked.reasons)

        allowed = self.gate.evaluate(
            mission=self.mission(
                terminal_state=TerminalState.BLOCKED_IRREDUCIBLY,
                irreducible_blocker="Provider does not expose the required operation.",
                exhaustion_evidence_ref="proof:route-exhaustion-1",
            )
        )
        self.assertTrue(allowed.allow_final)


class PreFinalInterlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state = DurableState(os.path.join(self.tmp.name, "prefinal.sqlite3"))
        self.interlock = ChatGovPreFinalInterlock(self.state)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_decision_is_checkpointed_and_metrics_are_updated(self) -> None:
        mission = MissionClosureState(
            mission_id="MISSION-DURABLE",
            objective="Do not stop while safe work remains",
            gaps=(
                GapState(
                    "KNOWN-GAP",
                    "Safe work remains",
                    route_known=True,
                    safe=True,
                    authorized=True,
                    available=True,
                ),
            ),
        )
        result = self.interlock.before_final_response(
            mission=mission,
            candidate_response="Everything is fully complete.",
        )
        self.assertFalse(result.final_response_allowed)
        self.assertTrue(result.auto_continue_required)
        checkpoint = self.state.latest_checkpoint(mission.mission_id)
        self.assertEqual(
            "PRE_FINAL_RESPONSE_DECISION", checkpoint["payload"]["event"]
        )
        self.assertEqual(1.0, self.state.metric("chatgov.prefinal.blocked"))
        self.assertEqual(1.0, self.state.metric("chatgov.prefinal.actionable_gaps"))
        self.assertEqual(1.0, self.state.metric("chatgov.prefinal.rewrite_required"))

    def test_verified_completion_checkpoint_is_proof_bearing(self) -> None:
        mission = MissionClosureState(
            mission_id="MISSION-COMPLETE",
            objective="Verified completion",
            terminal_state=TerminalState.VERIFIED_COMPLETE,
            objective_satisfied=True,
        )
        result = self.interlock.before_final_response(mission=mission)
        self.assertTrue(result.final_response_allowed)
        checkpoint = self.state.latest_checkpoint(mission.mission_id)
        self.assertEqual(1, checkpoint["proof_bearing"])


if __name__ == "__main__":
    unittest.main()
