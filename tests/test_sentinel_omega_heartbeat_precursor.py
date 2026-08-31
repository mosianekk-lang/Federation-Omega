import unittest
from datetime import datetime, timedelta, timezone

from federation.sentinel_omega.heartbeat_precursor import (
    CadenceState,
    HeartbeatCadenceForecaster,
)


UTC = timezone.utc
BASE = datetime(2026, 8, 31, 0, 0, tzinfo=UTC)


def timeline(minutes):
    current = BASE
    out = [current]
    for value in minutes:
        current += timedelta(minutes=value)
        out.append(current)
    return out


class HeartbeatCadenceForecasterTests(unittest.TestCase):
    def setUp(self):
        self.engine = HeartbeatCadenceForecaster(minimum_intervals=5)
        self.stable = timeline([60, 60, 60, 60, 60, 60, 60])

    def test_fit_learns_stable_hourly_cadence(self):
        profile = self.engine.fit(self.stable)
        self.assertEqual(profile.median_interval_seconds, 3600.0)
        self.assertEqual(profile.mad_seconds, 0.0)
        self.assertGreater(profile.watch_after_seconds, profile.median_interval_seconds)
        self.assertGreater(profile.precursor_after_seconds, profile.watch_after_seconds)
        self.assertGreater(profile.stale_after_seconds, profile.precursor_after_seconds)
        self.assertFalse(profile.recurrence_risk)

    def test_watch_precedes_precursor_and_stale(self):
        profile = self.engine.fit(self.stable)
        last = self.stable[-1]
        watch = self.engine.assess(
            "surface:sentinel",
            profile,
            last_seen_at=last,
            assessed_at=last + timedelta(seconds=profile.watch_after_seconds + 1),
        )
        precursor = self.engine.assess(
            "surface:sentinel",
            profile,
            last_seen_at=last,
            assessed_at=last + timedelta(seconds=profile.precursor_after_seconds + 1),
        )
        stale = self.engine.assess(
            "surface:sentinel",
            profile,
            last_seen_at=last,
            assessed_at=last + timedelta(seconds=profile.stale_after_seconds + 1),
        )
        self.assertEqual(watch.state, CadenceState.WATCH)
        self.assertEqual(precursor.state, CadenceState.PRECURSOR)
        self.assertEqual(stale.state, CadenceState.STALE)

    def test_long_gap_replay_enters_precursor_before_stale(self):
        # An anonymized approximately-hourly cohort with realistic jitter.
        profile = self.engine.fit(timeline([54, 64, 58, 65, 57, 60, 52, 70, 59]))
        last = timeline([54, 64, 58, 65, 57, 60, 52, 70, 59])[-1]
        result = self.engine.assess(
            "surface:sentinel",
            profile,
            last_seen_at=last,
            assessed_at=last + timedelta(minutes=90),
        )
        self.assertEqual(result.state, CadenceState.PRECURSOR)
        self.assertLess(profile.precursor_after_seconds, profile.stale_after_seconds)

    def test_recent_interval_expansion_creates_recurrence_prewarm(self):
        profile = self.engine.fit(timeline([60, 60, 60, 60, 60, 120]))
        self.assertTrue(profile.recurrence_risk)
        last = timeline([60, 60, 60, 60, 60, 120])[-1]
        result = self.engine.assess(
            "node:cfbe",
            profile,
            last_seen_at=last,
            assessed_at=last + timedelta(minutes=31),
        )
        self.assertEqual(result.state, CadenceState.WATCH)
        self.assertIn("RECURRENCE_PREWARM", result.reason_codes)

    def test_high_jitter_widens_warning_window(self):
        low = self.engine.fit(timeline([60, 60, 60, 60, 60, 60]))
        high = self.engine.fit(timeline([45, 75, 50, 70, 55, 65]))
        self.assertGreater(high.robust_jitter_seconds, low.robust_jitter_seconds)
        self.assertGreater(high.precursor_after_seconds, low.precursor_after_seconds)

    def test_non_monotonic_history_fails_closed(self):
        points = [
            BASE,
            BASE + timedelta(hours=1),
            BASE + timedelta(hours=2),
            BASE + timedelta(minutes=90),
        ]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            HeartbeatCadenceForecaster(minimum_intervals=3).fit(points)

    def test_insufficient_history_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "insufficient heartbeat history"):
            self.engine.fit(self.stable[:4])

    def test_assessment_before_last_seen_fails_closed(self):
        profile = self.engine.fit(self.stable)
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            self.engine.assess(
                "node:test",
                profile,
                last_seen_at=self.stable[-1],
                assessed_at=self.stable[-1] - timedelta(seconds=1),
            )

    def test_observation_requires_proof(self):
        profile = self.engine.fit(self.stable)
        assessment = self.engine.assess(
            "node:test",
            profile,
            last_seen_at=self.stable[-1],
            assessed_at=self.stable[-1] + timedelta(minutes=80),
        )
        with self.assertRaisesRegex(ValueError, "proof_refs"):
            self.engine.to_observation(assessment, proof_refs=())

    def test_observation_is_effect_free_and_preserves_precursor_state(self):
        profile = self.engine.fit(self.stable)
        assessment = self.engine.assess(
            "node:test",
            profile,
            last_seen_at=self.stable[-1],
            assessed_at=self.stable[-1] + timedelta(minutes=80),
        )
        observation = self.engine.to_observation(
            assessment,
            proof_refs=("heartbeat-ledger:A1", "snapshot:S1"),
        )
        self.assertFalse(observation.external_effect)
        self.assertEqual(observation.signal_kind.value, "HEALTH")
        self.assertEqual(observation.fingerprint, "HEARTBEAT_CADENCE_PRECURSOR")
        self.assertEqual(tuple(observation.proof_refs), ("heartbeat-ledger:A1", "snapshot:S1"))


if __name__ == "__main__":
    unittest.main()
