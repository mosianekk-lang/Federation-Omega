from __future__ import annotations

import unittest

from evidenceops.lex_omega.forest_first_health import (
    ForestFirstHealthInputs,
    ForestFirstHealthState,
    evaluate_forest_first_health,
)


def healthy_inputs(**overrides: bool) -> ForestFirstHealthInputs:
    data = dict(
        canonical_doctrine_readback=True,
        runtime_source_readback=True,
        private_state_readback=True,
        session_restore_verified=True,
        risk_vs_proof_control_loaded=True,
        merits_genome_control_loaded=True,
        legal_route_card_control_loaded=True,
        position_change_control_loaded=True,
        teach_back_control_loaded=True,
        pleading_integrity_control_loaded=True,
        jfrie_binding_loaded=True,
        continuity_control_loaded=True,
        latest_regression_passed=True,
    )
    data.update(overrides)
    return ForestFirstHealthInputs(**data)


class ForestFirstHealthAirlockTests(unittest.TestCase):
    def test_fully_evidenced_stack_is_active_verified(self) -> None:
        report = evaluate_forest_first_health(healthy_inputs(), consequential_legal_work=True)
        self.assertEqual(report.state, ForestFirstHealthState.ACTIVE_VERIFIED)
        self.assertEqual(report.status_line, "FOREST-FIRST: ACTIVE_VERIFIED")
        self.assertTrue(report.safe_for_consequential_legal_release)
        self.assertEqual(report.missing_controls, ())

    def test_verified_system_without_session_restore_is_visible_not_silently_active(self) -> None:
        report = evaluate_forest_first_health(
            healthy_inputs(session_restore_verified=False),
            consequential_legal_work=False,
        )
        self.assertEqual(report.state, ForestFirstHealthState.SYSTEM_READY_SESSION_NOT_RESTORED)
        self.assertFalse(report.safe_for_consequential_legal_release)
        self.assertIn("SESSION_RESTORE_VERIFIED", report.missing_controls)

    def test_missing_jfrie_blocks_high_stakes_release(self) -> None:
        report = evaluate_forest_first_health(
            healthy_inputs(jfrie_binding_loaded=False),
            consequential_legal_work=True,
        )
        self.assertEqual(report.state, ForestFirstHealthState.BLOCKED_HIGH_STAKES)
        self.assertIn("JFRIE_BINDING", report.blocking_controls)
        self.assertFalse(report.safe_for_consequential_legal_release)

    def test_missing_route_card_blocks_high_stakes_release(self) -> None:
        report = evaluate_forest_first_health(
            healthy_inputs(legal_route_card_control_loaded=False),
            consequential_legal_work=True,
        )
        self.assertEqual(report.state, ForestFirstHealthState.BLOCKED_HIGH_STAKES)
        self.assertIn("LEGAL_ROUTE_CARD_CONTROL", report.blocking_controls)

    def test_missing_teach_back_blocks_high_stakes_release(self) -> None:
        report = evaluate_forest_first_health(
            healthy_inputs(teach_back_control_loaded=False),
            consequential_legal_work=True,
        )
        self.assertEqual(report.state, ForestFirstHealthState.BLOCKED_HIGH_STAKES)
        self.assertIn("TEACH_BACK_CONTROL", report.blocking_controls)

    def test_unloaded_system_is_explicit(self) -> None:
        report = evaluate_forest_first_health(ForestFirstHealthInputs())
        self.assertEqual(report.state, ForestFirstHealthState.NOT_LOADED)
        self.assertFalse(report.safe_for_consequential_legal_release)

    def test_nonblocking_missing_control_is_degraded_not_falsely_active(self) -> None:
        report = evaluate_forest_first_health(
            healthy_inputs(position_change_control_loaded=False),
            consequential_legal_work=False,
        )
        self.assertEqual(report.state, ForestFirstHealthState.DEGRADED)
        self.assertIn("POSITION_CHANGE_CONTROL", report.missing_controls)
        self.assertFalse(report.safe_for_consequential_legal_release)


if __name__ == "__main__":
    unittest.main()
