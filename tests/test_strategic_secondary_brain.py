import math
import unittest

from federation_consolidation.strategic_secondary_brain import (
    ActionDisposition,
    AuthorityClass,
    StrategicCompiler,
    StrategicHypothesis,
    StrategicOption,
    StrategicSignal,
    StrategicTemperature,
    brier_score,
    surprise_score,
)


def _signal(signal_id="S1", **kw):
    base = dict(
        source="public-signal",
        observed_at=1.0,
        summary="Competitor adds a new agent governance API",
        credibility=.9,
        surprise=.8,
        impact=.9,
        tags=("agents", "governance"),
    )
    base.update(kw)
    return StrategicSignal(signal_id=signal_id, **base)


def _hypothesis():
    return StrategicHypothesis(
        "H1",
        "Enterprise agent governance is becoming a platform primitive",
        .72,
        ("No production controls emerge within 180 days",),
        ("S1",),
        180,
    )


def _option(authority=AuthorityClass.A1, option_id="O1", expected_value=10):
    return StrategicOption(
        option_id,
        "Build provider-neutral governance challenger in shadow mode",
        expected_value,
        4,
        3,
        1,
        .1,
        .1,
        .1,
        authority,
        "Ω32→Ω25→Ω8",
        "research-only",
        "shadow benchmark plus semantic readback",
        "discard challenger; preserve evidence",
    )


class StrategicSecondaryBrainTests(unittest.TestCase):
    def test_dedup_keeps_stronger_evidence(self):
        out = StrategicCompiler().deduplicate(
            [_signal("S0", credibility=.4), _signal("S1", credibility=.95)]
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].signal_id, "S1")

    def test_material_without_hypothesis_routes_to_research(self):
        packet = StrategicCompiler().compile(
            signals=[_signal()], hypotheses=[], options=[], now=2
        )
        self.assertIs(packet.disposition, ActionDisposition.RESEARCH)
        self.assertIn(
            packet.temperature,
            (StrategicTemperature.HOT, StrategicTemperature.CRITICAL),
        )

    def test_safe_option_is_queued(self):
        packet = StrategicCompiler().compile(
            signals=[_signal()], hypotheses=[_hypothesis()], options=[_option()], now=2
        )
        self.assertIs(packet.disposition, ActionDisposition.QUEUE_SAFE)
        self.assertIs(packet.authority, AuthorityClass.A1)
        self.assertEqual(packet.selected_option_id, "O1")

    def test_a2_option_is_held(self):
        packet = StrategicCompiler().compile(
            signals=[_signal()],
            hypotheses=[_hypothesis()],
            options=[_option(AuthorityClass.A2)],
            now=2,
        )
        self.assertIs(packet.disposition, ActionDisposition.HOLD_AUTHORITY)

    def test_highest_risk_adjusted_value_wins(self):
        packet = StrategicCompiler().compile(
            signals=[_signal()],
            hypotheses=[_hypothesis()],
            options=[
                _option(option_id="LOW", expected_value=3),
                _option(option_id="HIGH", expected_value=12),
            ],
            now=2,
        )
        self.assertEqual(packet.selected_option_id, "HIGH")

    def test_forecast_metrics(self):
        self.assertAlmostEqual(brier_score(.8, True), .04)
        self.assertAlmostEqual(surprise_score(.5, True), 1.0)
        self.assertTrue(math.isfinite(surprise_score(.001, False)))


if __name__ == "__main__":
    unittest.main()
