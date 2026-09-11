import unittest

from fuse_astra_signal_temporal.signal import (
    ChangeDetector,
    SignalCorrelator,
    SignalFusionEngine,
    SignalGate,
    SignalKind,
    SignalObservation,
    SourceQuality,
)
from fuse_astra_signal_temporal.temporal import (
    BitemporalFact,
    BitemporalStore,
    HybridLogicalClock,
    HybridTimestamp,
    SequenceState,
    StreamTimeTracker,
    TemporalPolicy,
    TemporalSemantics,
    Timeliness,
)


class SignalTemporalTests(unittest.TestCase):
    def test_echo_sources_do_not_count_as_independent_corroboration(self):
        obs = [
            SignalObservation("a1", "src-a", "family-x", SignalKind.EVENT, "risk", 1000, 1010, confidence=.9),
            SignalObservation("a2", "src-a-mirror", "family-x", SignalKind.EVENT, "risk", 1000, 1010, confidence=.8),
        ]
        q = {
            "src-a": SourceQuality("src-a"),
            "src-a-mirror": SourceQuality("src-a-mirror"),
        }
        fused = SignalFusionEngine().fuse("risk", obs, q, now_ms=1100)
        self.assertEqual(fused.independent_groups, 1)
        self.assertFalse(SignalGate.qualified(fused, min_confidence=.5, min_independent_groups=2))

    def test_independent_sources_raise_confidence(self):
        obs = [
            SignalObservation("a1", "src-a", "g1", SignalKind.EVENT, "risk", 1000, 1010, confidence=.7),
            SignalObservation("b1", "src-b", "g2", SignalKind.EVENT, "risk", 1002, 1012, confidence=.7),
        ]
        q = {"src-a": SourceQuality("src-a"), "src-b": SourceQuality("src-b")}
        fused = SignalFusionEngine().fuse("risk", obs, q, now_ms=1015)
        self.assertEqual(fused.independent_groups, 2)
        self.assertGreater(fused.confidence, .7)

    def test_temporal_proximity_is_not_upgraded_to_causation(self):
        obs = [
            SignalObservation("a", "s1", "g1", SignalKind.EVENT, "x", 1000, 1010),
            SignalObservation("b", "s2", "g2", SignalKind.EVENT, "x", 1010, 1020),
        ]
        links = SignalCorrelator().correlate(obs, max_delta_ms=50)
        self.assertEqual(links[0].relation, "TEMPORAL_CORRELATION")

    def test_explicit_causation_is_preserved(self):
        obs = [
            SignalObservation("a", "s1", "g1", SignalKind.EVENT, "x", 1000, 1010),
            SignalObservation("b", "s2", "g2", SignalKind.EVENT, "y", 1010, 1020, causation_id="a"),
        ]
        links = SignalCorrelator().correlate(obs, max_delta_ms=50)
        self.assertEqual(links[0].relation, "EXPLICIT_CAUSATION")

    def test_change_detector_flags_large_shift(self):
        changed, z = ChangeDetector.zscore_change([10, 11, 9, 10], 30, threshold=3)
        self.assertTrue(changed)
        self.assertGreater(z, 3)

    def test_watermark_classifies_late_event_without_reordering_truth(self):
        tracker = StreamTimeTracker(TemporalPolicy(allowed_lateness_ms=100, late_grace_ms=50))
        first = tracker.observe("s", event_time_ms=1000, observed_time_ms=1010, sequence=1)
        second = tracker.observe("s", event_time_ms=1200, observed_time_ms=1210, sequence=2)
        late = tracker.observe("s", event_time_ms=1080, observed_time_ms=1220, sequence=3)
        self.assertEqual(first.timeliness, Timeliness.ON_TIME)
        self.assertEqual(second.watermark_after_ms, 1100)
        self.assertEqual(late.timeliness, Timeliness.LATE_ACCEPTED)

    def test_too_late_and_sequence_gap_are_distinct(self):
        tracker = StreamTimeTracker(TemporalPolicy(allowed_lateness_ms=100, late_grace_ms=10))
        tracker.observe("s", event_time_ms=1000, observed_time_ms=1010, sequence=1)
        tracker.observe("s", event_time_ms=1300, observed_time_ms=1310, sequence=2)
        r = tracker.observe("s", event_time_ms=1100, observed_time_ms=1320, sequence=4)
        self.assertEqual(r.timeliness, Timeliness.TOO_LATE)
        self.assertEqual(r.sequence_state, SequenceState.GAP)

    def test_future_clock_skew_is_explicit(self):
        tracker = StreamTimeTracker(TemporalPolicy(max_future_skew_ms=50))
        r = tracker.observe("s", event_time_ms=1100, observed_time_ms=1000)
        self.assertEqual(r.timeliness, Timeliness.FUTURE_SKEW)

    def test_hybrid_logical_clock_orders_concurrent_wall_time(self):
        c = HybridLogicalClock()
        a = c.send(1000)
        b = c.send(1000)
        self.assertLess(a, b)
        remote = HybridTimestamp(1000, 10)
        merged = c.recv(remote, 999)
        self.assertEqual(merged.physical_ms, 1000)
        self.assertGreater(merged.logical, 10)

    def test_bitemporal_query_reconstructs_what_was_known_then(self):
        store = BitemporalStore()
        store.add(BitemporalFact("f1", "svc", "status", "up", 0, None, 100))
        store.add(BitemporalFact("f2", "svc", "status", "degraded", 50, None, 200))
        then = store.as_of(subject="svc", predicate="status", valid_ms=75, transaction_ms=150)
        later = store.as_of(subject="svc", predicate="status", valid_ms=75, transaction_ms=250)
        self.assertEqual(then.value, "up")
        self.assertEqual(later.value, "degraded")

    def test_tumbling_window_is_event_time_based(self):
        self.assertEqual(TemporalSemantics.window_start(12_345, width_ms=5_000), 10_000)

    def test_deadline_expiry_and_staleness_are_separate(self):
        state = TemporalSemantics.classify_deadline(
            now_ms=1000, deadline_ms=900, expires_ms=1200, freshness_ms=100, observed_ms=800
        )
        self.assertTrue(state.due)
        self.assertFalse(state.expired)
        self.assertTrue(state.stale)


if __name__ == "__main__":
    unittest.main()
