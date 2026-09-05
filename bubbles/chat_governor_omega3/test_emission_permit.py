from __future__ import annotations

import unittest

from .emission_permit import FinalResponsePermitAuthority
from .pre_final import MissionClosureState, PreFinalGate, TerminalState


class FinalResponsePermitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = PreFinalGate()
        self.permits = FinalResponsePermitAuthority()
        self.mission = MissionClosureState(
            mission_id="MISSION-PERMIT",
            objective="Finish with truthful final output",
            terminal_state=TerminalState.VERIFIED_COMPLETE,
            objective_satisfied=True,
        )
        self.candidate = "Verified outcome: the bounded mission is complete."
        self.decision = self.gate.evaluate(
            mission=self.mission,
            candidate_response=self.candidate,
        )

    def test_permit_requires_allow_decision(self) -> None:
        active = MissionClosureState(
            mission_id="MISSION-ACTIVE",
            objective="Keep working",
        )
        blocked = self.gate.evaluate(mission=active)
        with self.assertRaisesRegex(
            ValueError, "FINAL_RESPONSE_PERMIT_REQUIRES_ALLOW_DECISION"
        ):
            self.permits.issue(
                decision=blocked,
                mission=active,
                candidate_response="Stopping now.",
            )

    def test_exact_candidate_and_mission_validate(self) -> None:
        permit = self.permits.issue(
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        validation = self.permits.validate(
            permit=permit,
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        self.assertTrue(validation.valid)
        self.assertEqual((), validation.reasons)

    def test_candidate_mutation_after_gate_fails_closed(self) -> None:
        permit = self.permits.issue(
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        validation = self.permits.validate(
            permit=permit,
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate + " It is universally operational.",
        )
        self.assertFalse(validation.valid)
        self.assertIn(
            "CANDIDATE_CHANGED_AFTER_PREFINAL_APPROVAL", validation.reasons
        )

    def test_mission_mutation_after_gate_fails_closed(self) -> None:
        permit = self.permits.issue(
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        changed = MissionClosureState(
            mission_id="MISSION-PERMIT",
            objective="Finish with truthful final output",
            terminal_state=TerminalState.VERIFIED_COMPLETE,
            objective_satisfied=True,
            currently_executable_work=True,
        )
        validation = self.permits.validate(
            permit=permit,
            decision=self.decision,
            mission=changed,
            candidate_response=self.candidate,
        )
        self.assertFalse(validation.valid)
        self.assertIn(
            "MISSION_STATE_CHANGED_AFTER_PREFINAL_APPROVAL", validation.reasons
        )

    def test_decision_swap_after_gate_fails_closed(self) -> None:
        permit = self.permits.issue(
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        second_decision = self.gate.evaluate(
            mission=self.mission,
            candidate_response="A different safe final response.",
        )
        validation = self.permits.validate(
            permit=permit,
            decision=second_decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        self.assertFalse(validation.valid)
        self.assertIn("PERMIT_DECISION_MISMATCH", validation.reasons)

    def test_telemetry_is_explicitly_non_exporting_schema(self) -> None:
        permit = self.permits.issue(
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        validation = self.permits.validate(
            permit=permit,
            decision=self.decision,
            mission=self.mission,
            candidate_response=self.candidate,
        )
        attrs = self.permits.telemetry_attributes(
            permit=permit, validation=validation
        )
        self.assertTrue(attrs["chatgov.emission.valid"])
        self.assertEqual(permit.permit_id, attrs["chatgov.emission.permit_id"])


if __name__ == "__main__":
    unittest.main()
