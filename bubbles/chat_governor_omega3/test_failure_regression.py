from __future__ import annotations

import unittest

from .failure_regression import compile_prefinal_regression
from .pre_final import GapState, MissionClosureState, PreFinalGate


class FailureRegressionCompilerTests(unittest.TestCase):
    def test_actionable_gap_becomes_f19_regression(self) -> None:
        mission = MissionClosureState(
            mission_id="MISSION-REGRESSION",
            objective="Do not terminate while safe work remains",
            gaps=(
                GapState(
                    gap_id="RUNTIME-BIND",
                    summary="Safe runtime binding remains",
                    route_known=True,
                    safe=True,
                    authorized=True,
                    available=True,
                ),
            ),
        )
        candidate = "The architecture is complete; the runtime binding is the next step."
        decision = PreFinalGate().evaluate(
            mission=mission,
            candidate_response=candidate,
        )
        case = compile_prefinal_regression(
            mission=mission,
            candidate_response=candidate,
            decision=decision,
        )
        self.assertIn(
            "F19_KNOWN_ACTIONABLE_GAP_PREMATURE_TERMINATION",
            case.failure_classes,
        )
        self.assertFalse(case.expected_allow_final)
        self.assertTrue(case.expected_continue_work)
        self.assertTrue(case.case_id.startswith("pfr_"))

    def test_maturity_claim_without_scan_becomes_f24(self) -> None:
        mission = MissionClosureState(
            mission_id="MISSION-MATURITY",
            objective="Report only proven maturity",
        )
        candidate = "The system is fully operational."
        decision = PreFinalGate().evaluate(
            mission=mission,
            candidate_response=candidate,
        )
        case = compile_prefinal_regression(
            mission=mission,
            candidate_response=candidate,
            decision=decision,
        )
        self.assertIn(
            "F24_MATURITY_CLAIM_WITHOUT_CLAIM_PROOF_SCAN",
            case.failure_classes,
        )
        record = case.as_dataset_record()
        self.assertEqual(case.case_id, record["case_id"])
        self.assertEqual(candidate, record["candidate_response"])


if __name__ == "__main__":
    unittest.main()
