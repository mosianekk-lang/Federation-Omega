import unittest

from fuse_astra_signal_temporal.anticipation import (
    EarlyWarningEngine,
    ForecastEngine,
    LeadLagAnalyzer,
    OpportunityClassifier,
    OpportunityPhase,
    Regime,
    RegimeClassifier,
    TemporalAction,
    TemporalActionAdvisor,
    TimeValue,
    TrendDirection,
    TrendEstimator,
)


class AnticipationTests(unittest.TestCase):
    def test_rising_trend(self):
        points = [TimeValue(0, 1), TimeValue(1000, 2), TimeValue(2000, 3)]
        trend = TrendEstimator.fit(points)
        self.assertEqual(trend.direction, TrendDirection.RISING)
        self.assertAlmostEqual(trend.r2, 1.0)

    def test_linear_forecast_extrapolates_with_confidence(self):
        points = [TimeValue(0, 1), TimeValue(1000, 2), TimeValue(2000, 3)]
        f = ForecastEngine.linear(points, target_time_ms=3000)
        self.assertAlmostEqual(f.estimate, 4.0)
        self.assertGreater(f.confidence, 0.0)

    def test_leading_series_detected(self):
        leading = [0, 1, 2, 3, 4, 5, 6]
        target = [9, 9, 0, 1, 2, 3, 4]
        est = LeadLagAnalyzer.best_lag(leading, target, max_lag_steps=3)
        self.assertEqual(est.lag_steps, 2)
        self.assertAlmostEqual(est.correlation, 1.0)

    def test_regime_elevated(self):
        r = RegimeClassifier.classify([9, 10, 11, 10], [20, 21, 19, 20], shift_z=2)
        self.assertEqual(r.regime, Regime.ELEVATED)

    def test_regime_volatile_precedes_mean_shift_label(self):
        r = RegimeClassifier.classify([9, 10, 11, 10], [0, 20, 0, 20], volatility_multiplier=2)
        self.assertEqual(r.regime, Regime.VOLATILE)

    def test_early_warning_estimates_lead_time(self):
        e = EarlyWarningEngine.score(
            fused_confidence=.9,
            salience=.8,
            lead_lag_correlation=.7,
            persistence=.8,
            threshold_distance=10,
            estimated_rate_per_ms=.01,
        )
        self.assertEqual(e.lead_time_ms, 1000)
        self.assertGreater(e.probability, .7)

    def test_stale_evidence_forces_investigation(self):
        a = TemporalActionAdvisor.advise(
            probability=.95,
            confidence=.95,
            lead_time_ms=1000,
            failure_cost=.9,
            reversibility=.9,
            authority_ready=True,
            evidence_fresh=False,
        )
        self.assertEqual(a, TemporalAction.INVESTIGATE)

    def test_missing_authority_holds_high_risk_action(self):
        a = TemporalActionAdvisor.advise(
            probability=.95,
            confidence=.9,
            lead_time_ms=1000,
            failure_cost=.9,
            reversibility=.8,
            authority_ready=False,
            evidence_fresh=True,
        )
        self.assertEqual(a, TemporalAction.HOLD)

    def test_high_confidence_reversible_authorized_warning_can_act(self):
        a = TemporalActionAdvisor.advise(
            probability=.95,
            confidence=.95,
            lead_time_ms=1000,
            failure_cost=.9,
            reversibility=.9,
            authority_ready=True,
            evidence_fresh=True,
        )
        self.assertEqual(a, TemporalAction.ACT)

    def test_actionable_opportunity(self):
        p = OpportunityClassifier.classify(momentum=.8, evidence=.8, adoption=.5, saturation=.4, decay=.1)
        self.assertEqual(p, OpportunityPhase.ACTIONABLE)

    def test_crowded_opportunity(self):
        p = OpportunityClassifier.classify(momentum=.8, evidence=.9, adoption=.9, saturation=.9, decay=.1)
        self.assertEqual(p, OpportunityPhase.CROWDED)

    def test_expired_opportunity(self):
        p = OpportunityClassifier.classify(momentum=.1, evidence=.8, adoption=.8, saturation=.9, decay=.9)
        self.assertEqual(p, OpportunityPhase.EXPIRED)


if __name__ == "__main__":
    unittest.main()
