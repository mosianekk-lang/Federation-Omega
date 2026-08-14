from __future__ import annotations

import unittest

from evidenceops.lex_omega import AnticipatoryContext, ForestFirstAnticipatoryEngine


class ForestFirstAnticipatoryAirlockIntegrationTests(unittest.TestCase):
    def test_high_stakes_preflight_surfaces_multiple_future_needs(self) -> None:
        report = ForestFirstAnticipatoryEngine().evaluate(
            AnticipatoryContext(
                high_stakes=True,
                credible_risk_signal_present=True,
                consequential_action_planned=True,
                legal_route_complete=False,
                teach_back_complete=False,
                deadline_state_verified=False,
                evidence_preservation_current=False,
                continuity_checkpoint_current=False,
                best_current_version_gate_passed=False,
                provider_readback_required_but_missing=True,
            )
        )
        self.assertGreaterEqual(len(report.cues), 7)
        self.assertTrue(report.user_interrupt_required)
        self.assertEqual(report.highest_priority, 5)


if __name__ == "__main__":
    unittest.main()
