from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.input_compiler_challenger_v21 import compile_owner_input_v21
from benchmarking.cfbe_omega.input_compiler_fidelity_v1 import evaluate_suite, load_cases
from federation.cfbe_input_compiler_v2 import compile_owner_input


class CFBEInputCompilerFidelityV1Tests(unittest.TestCase):
    def test_fixture_is_public_safe_and_diverse(self) -> None:
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 18)
        intents = {str(case["expected_intent"]) for case in cases}
        self.assertTrue({"CONTINUE", "FIX", "IMPROVE", "INVESTIGATE", "BUILD", "EXECUTE_ALL", "CHALLENGE", "GENERAL"}.issubset(intents))

    def test_v2_incumbent_gaps_are_reproduced_without_hard_safety_failure(self) -> None:
        report = evaluate_suite(compiler=compile_owner_input, compiler_name="V2_INCUMBENT")
        self.assertEqual(report.status, "GAPS_CONFIRMED")
        self.assertEqual(report.hard_veto_count, 0)
        self.assertEqual(report.failed_case_ids, ("F04", "F05", "F06", "F07", "F08", "F11"))
        self.assertEqual(report.intent_accuracy, 0.666667)
        self.assertEqual(report.effect_accuracy, 0.944444)
        self.assertEqual(report.approval_accuracy, 1.0)
        self.assertEqual(report.clarification_accuracy, 1.0)
        self.assertEqual(report.mission_ir_validity, 1.0)
        self.assertEqual(report.deterministic_rate, 1.0)

    def test_v21_challenger_clears_fidelity_court(self) -> None:
        report = evaluate_suite(compiler=compile_owner_input_v21, compiler_name="V2.1_CHALLENGER")
        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.passed_cases, report.case_count)
        self.assertEqual(report.failed_case_ids, ())
        self.assertEqual(report.hard_veto_count, 0)
        self.assertEqual(report.intent_accuracy, 1.0)
        self.assertEqual(report.effect_accuracy, 1.0)
        self.assertEqual(report.approval_accuracy, 1.0)
        self.assertEqual(report.clarification_accuracy, 1.0)
        self.assertEqual(report.capability_coverage, 1.0)
        self.assertEqual(report.workstream_coverage, 1.0)
        self.assertEqual(report.mission_ir_validity, 1.0)
        self.assertEqual(report.deterministic_rate, 1.0)

    def test_challenger_preserves_consequential_authority_gate(self) -> None:
        report = evaluate_suite(compiler=compile_owner_input_v21, compiler_name="V2.1_CHALLENGER")
        for result in report.results:
            if result.case_id in {"F14", "F15", "F18"}:
                self.assertTrue(result.effect_ok)
                self.assertTrue(result.approval_ok)
                self.assertFalse(result.hard_veto)

    def test_context_free_n_remains_fail_closed(self) -> None:
        report = evaluate_suite(compiler=compile_owner_input_v21, compiler_name="V2.1_CHALLENGER")
        result = next(item for item in report.results if item.case_id == "F02")
        self.assertTrue(result.clarification_ok)
        self.assertFalse(result.hard_veto)


if __name__ == "__main__":
    unittest.main()
