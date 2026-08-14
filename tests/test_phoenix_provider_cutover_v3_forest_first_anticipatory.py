from __future__ import annotations

import unittest

from evidenceops.lex_omega import (
    ActionClass,
    AnticipatoryContext,
    ForestFirstAnticipatoryEngine,
    NeedClass,
)


class ForestFirstAnticipatoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ForestFirstAnticipatoryEngine()

    def test_healthy_context_is_quiet(self) -> None:
        report = self.engine.evaluate(AnticipatoryContext())
        self.assertTrue(report.quiet_when_healthy)
        self.assertFalse(report.user_interrupt_required)
        self.assertEqual(report.cues, ())

    def test_risk_signal_triggers_protective_preparation_without_accusation(self) -> None:
        report = self.engine.evaluate(
            AnticipatoryContext(
                high_stakes=True,
                credible_risk_signal_present=True,
                trigger_refs=("USER-RISK-001",),
            )
        )
        risk = [cue for cue in report.cues if cue.need_class is NeedClass.RISK]
        self.assertEqual(len(risk), 1)
        self.assertEqual(risk[0].action_class, ActionClass.AUTO_SAFE_INTERNAL)
        self.assertIn("competing explanations", risk[0].recommended_action)
        self.assertFalse(report.user_interrupt_required)

    def test_consequential_action_without_route_is_held(self) -> None:
        report = self.engine.evaluate(
            AnticipatoryContext(
                high_stakes=True,
                consequential_action_planned=True,
                legal_route_complete=False,
            )
        )
        quality = [cue for cue in report.cues if cue.need_class is NeedClass.QUALITY]
        self.assertTrue(any(cue.action_class is ActionClass.PREPARE_AND_HOLD for cue in quality))

    def test_teach_back_only_interrupts_when_owner_understanding_is_required(self) -> None:
        report = self.engine.evaluate(
            AnticipatoryContext(
                high_stakes=True,
                consequential_action_planned=True,
                teach_back_complete=False,
            )
        )
        self.assertTrue(report.user_interrupt_required)
        self.assertTrue(report.owner_decisions)

    def test_material_correction_creates_learning_action(self) -> None:
        report = self.engine.evaluate(
            AnticipatoryContext(material_user_correction_received=True)
        )
        learning = [cue for cue in report.cues if cue.need_class is NeedClass.LEARNING]
        self.assertEqual(len(learning), 1)
        self.assertIn("regression candidate", learning[0].recommended_action)

    def test_repeated_failure_blocks_unchanged_retry(self) -> None:
        report = self.engine.evaluate(
            AnticipatoryContext(repeated_failure_detected=True)
        )
        automation = [cue for cue in report.cues if cue.need_class is NeedClass.AUTOMATION]
        self.assertEqual(len(automation), 1)
        self.assertIn("Stop unchanged retries", automation[0].recommended_action)

    def test_best_version_gate_is_automatic_not_user_prompt_dependent(self) -> None:
        report = self.engine.evaluate(
            AnticipatoryContext(best_current_version_gate_passed=False)
        )
        quality = [cue for cue in report.cues if cue.need_class is NeedClass.QUALITY]
        self.assertEqual(len(quality), 1)
        self.assertEqual(quality[0].action_class, ActionClass.AUTO_SAFE_INTERNAL)
        self.assertIn("Best Current Verified Version", quality[0].description)

    def test_missing_provider_readback_holds_terminal_claim(self) -> None:
        report = self.engine.evaluate(
            AnticipatoryContext(provider_readback_required_but_missing=True)
        )
        self.assertTrue(any(
            cue.action_class is ActionClass.PREPARE_AND_HOLD
            and "provider readback" in cue.description
            for cue in report.cues
        ))


if __name__ == "__main__":
    unittest.main()
