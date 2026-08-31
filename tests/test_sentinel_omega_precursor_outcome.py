import unittest
from datetime import datetime, timedelta, timezone

from federation.sentinel_omega.heartbeat_precursor import HeartbeatCadenceForecaster
from federation.sentinel_omega.precursor_outcome import (
    PredictionOutcome,
    PrecursorCohortEvaluator,
    PrecursorOutcomeEvidence,
    PrecursorOutcomeResolver,
    PrecursorPrediction,
)

UTC = timezone.utc
BASE = datetime(2026, 8, 31, 0, 0, tzinfo=UTC)


def stable_history():
    return [BASE + timedelta(hours=i) for i in range(8)]


def prediction_at(minutes_after_last=70, prediction_id="P1"):
    engine = HeartbeatCadenceForecaster(minimum_intervals=5)
    history = stable_history()
    profile = engine.fit(history)
    assessment = engine.assess(
        "surface:sentinel",
        profile,
        last_seen_at=history[-1],
        assessed_at=history[-1] + timedelta(minutes=minutes_after_last),
    )
    return PrecursorPrediction.from_assessment(
        assessment,
        prediction_id=prediction_id,
        model_schema="SENTINEL-OMEGA-HEARTBEAT-PRECURSOR-V1",
        source_sha="abc123",
        sample_count=profile.interval_count,
        median_interval_seconds=profile.median_interval_seconds,
        mad_seconds=profile.mad_seconds,
        jitter_seconds=profile.robust_jitter_seconds,
        proof_refs=("hb:history", "source:abc123"),
    )


class PrecursorPredictionTests(unittest.TestCase):
    def test_healthy_assessment_cannot_be_registered_as_warning(self):
        engine = HeartbeatCadenceForecaster(minimum_intervals=5)
        history = stable_history()
        profile = engine.fit(history)
        assessment = engine.assess(
            "surface:sentinel", profile, last_seen_at=history[-1], assessed_at=history[-1] + timedelta(minutes=20)
        )
        with self.assertRaisesRegex(ValueError, "healthy"):
            PrecursorPrediction.from_assessment(
                assessment,
                prediction_id="healthy",
                model_schema="v1",
                source_sha="abc",
                sample_count=profile.interval_count,
                median_interval_seconds=profile.median_interval_seconds,
                mad_seconds=profile.mad_seconds,
                jitter_seconds=profile.robust_jitter_seconds,
                proof_refs=("proof:1",),
            )

    def test_prediction_requires_five_intervals_and_proof(self):
        p = prediction_at()
        self.assertGreaterEqual(p.sample_count, 5)
        self.assertTrue(p.proof_refs)
        self.assertFalse(p.external_effect)


class PrecursorOutcomeResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = PrecursorOutcomeResolver()

    def test_watch_then_heartbeat_before_precursor_is_on_time_after_warning(self):
        p = prediction_at(70)
        heartbeat = datetime.fromisoformat(p.precursor_at) - timedelta(seconds=1)
        result = self.resolver.resolve(
            p,
            PrecursorOutcomeEvidence(
                observed_at=heartbeat.isoformat(),
                next_heartbeat_at=heartbeat.isoformat(),
                proof_refs=("hb:return",),
            ),
        )
        self.assertEqual(result.outcome, PredictionOutcome.ON_TIME_AFTER_WARNING)
        self.assertFalse(result.prevention_claim)

    def test_precursor_then_heartbeat_before_stale_is_recovered(self):
        p = prediction_at(80)
        heartbeat = datetime.fromisoformat(p.stale_at) - timedelta(seconds=1)
        result = self.resolver.resolve(
            p,
            PrecursorOutcomeEvidence(
                observed_at=heartbeat.isoformat(),
                next_heartbeat_at=heartbeat.isoformat(),
                proof_refs=("hb:recovery",),
            ),
        )
        self.assertEqual(result.outcome, PredictionOutcome.RECOVERED_AFTER_WARNING)

    def test_stale_confirmation_is_confirmed_miss(self):
        p = prediction_at(80)
        observed = datetime.fromisoformat(p.stale_at) + timedelta(minutes=5)
        result = self.resolver.resolve(
            p,
            PrecursorOutcomeEvidence(
                observed_at=observed.isoformat(),
                stale_confirmed=True,
                proof_refs=("snapshot:stale",),
            ),
        )
        self.assertEqual(result.outcome, PredictionOutcome.MISSED_OR_STALE_CONFIRMED)

    def test_late_heartbeat_after_stale_also_confirms_miss(self):
        p = prediction_at(80)
        heartbeat = datetime.fromisoformat(p.stale_at) + timedelta(minutes=20)
        result = self.resolver.resolve(
            p,
            PrecursorOutcomeEvidence(
                observed_at=heartbeat.isoformat(),
                next_heartbeat_at=heartbeat.isoformat(),
                proof_refs=("hb:late",),
            ),
        )
        self.assertEqual(result.outcome, PredictionOutcome.MISSED_OR_STALE_CONFIRMED)

    def test_verified_intentional_pause_is_censored_not_false_positive(self):
        p = prediction_at(80)
        result = self.resolver.resolve(
            p,
            PrecursorOutcomeEvidence(
                observed_at=(datetime.fromisoformat(p.assessed_at) + timedelta(minutes=5)).isoformat(),
                intentional_pause_verified=True,
                proof_refs=("control:pause",),
            ),
        )
        self.assertEqual(result.outcome, PredictionOutcome.CENSORED_INSUFFICIENT_FOLLOWUP)

    def test_false_positive_requires_explicit_verified_evidence(self):
        p = prediction_at(80)
        result = self.resolver.resolve(
            p,
            PrecursorOutcomeEvidence(
                observed_at=(datetime.fromisoformat(p.assessed_at) + timedelta(minutes=5)).isoformat(),
                false_positive_verified=True,
                proof_refs=("verifier:false-positive",),
            ),
        )
        self.assertEqual(result.outcome, PredictionOutcome.FALSE_POSITIVE_VERIFIED)

    def test_repair_does_not_create_prevention_claim(self):
        p = prediction_at(80)
        heartbeat = datetime.fromisoformat(p.stale_at) - timedelta(minutes=1)
        result = self.resolver.resolve(
            p,
            PrecursorOutcomeEvidence(
                observed_at=heartbeat.isoformat(),
                next_heartbeat_at=heartbeat.isoformat(),
                repair_applied=True,
                proof_refs=("repair:r1", "hb:after-repair"),
            ),
        )
        self.assertTrue(result.repair_applied)
        self.assertFalse(result.prevention_claim)


class PrecursorCohortEvaluatorTests(unittest.TestCase):
    def _resolved(self, idx, *, stale=False, false_positive=False, owner=0.0):
        p = prediction_at(80, f"P{idx}")
        resolver = PrecursorOutcomeResolver()
        if false_positive:
            evidence = PrecursorOutcomeEvidence(
                observed_at=(datetime.fromisoformat(p.assessed_at) + timedelta(minutes=2)).isoformat(),
                false_positive_verified=True,
                owner_intervention_seconds=owner,
                proof_refs=(f"proof:{idx}",),
            )
        elif stale:
            evidence = PrecursorOutcomeEvidence(
                observed_at=(datetime.fromisoformat(p.stale_at) + timedelta(minutes=1)).isoformat(),
                stale_confirmed=True,
                owner_intervention_seconds=owner,
                proof_refs=(f"proof:{idx}",),
            )
        else:
            heartbeat = datetime.fromisoformat(p.stale_at) - timedelta(minutes=1)
            evidence = PrecursorOutcomeEvidence(
                observed_at=heartbeat.isoformat(),
                next_heartbeat_at=heartbeat.isoformat(),
                owner_intervention_seconds=owner,
                proof_refs=(f"proof:{idx}",),
            )
        return resolver.resolve(p, evidence)

    def test_accuracy_gate_requires_minimum_resolved_prospective_sample(self):
        evaluator = PrecursorCohortEvaluator(minimum_accuracy_samples=10)
        nine = tuple(self._resolved(i, stale=(i % 3 == 0)) for i in range(9))
        ten = nine + (self._resolved(9, false_positive=True),)
        self.assertFalse(evaluator.evaluate(nine).accuracy_claim_allowed)
        metrics = evaluator.evaluate(ten)
        self.assertTrue(metrics.accuracy_claim_allowed)
        self.assertFalse(metrics.prevention_value_claim_allowed)
        self.assertEqual(metrics.prediction_count, 10)
        self.assertEqual(metrics.verified_false_positive_count, 1)

    def test_duplicate_prediction_outcomes_fail_closed(self):
        item = self._resolved(1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            PrecursorCohortEvaluator().evaluate((item, item))

    def test_owner_intervention_metric_is_observed_not_inferred(self):
        metrics = PrecursorCohortEvaluator(minimum_accuracy_samples=5).evaluate(
            tuple(self._resolved(i, owner=float(i * 10)) for i in range(5))
        )
        self.assertEqual(metrics.median_owner_intervention_seconds, 20.0)
        self.assertFalse(metrics.prevention_value_claim_allowed)


if __name__ == "__main__":
    unittest.main()
