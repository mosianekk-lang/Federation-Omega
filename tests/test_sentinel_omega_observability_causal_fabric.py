import unittest

from federation.living_state.model import LivingWorldModel
from federation.living_state.types import (
    EdgeKind,
    NodeKind,
    ProofMaturity,
    Provenance,
    WorldEdge,
    WorldNode,
)
from federation.sentinel_omega import (
    AdaptiveBaselineDetector,
    IncidentCorrelator,
    MultiWindowSLOGuard,
    NormalizedObservation,
    SemanticObservationNormalizer,
    SentinelObservabilityCausalFabric,
    SignalKind,
    SLOWindowSample,
)


NOW = "2026-08-31T20:20:00+00:00"


def provenance(ref: str) -> Provenance:
    return Provenance(
        source_ref=f"source:{ref}",
        proof_ref=f"proof:{ref}",
        observed_at=NOW,
        proof_maturity=ProofMaturity.DETERMINISTIC_TESTED,
        ttl_seconds=3600,
        confidence=0.9,
    )


def world() -> LivingWorldModel:
    model = LivingWorldModel()
    for node_id in ("service:api", "service:worker", "service:db"):
        model.observe_node(WorldNode(node_id, NodeKind.SYSTEM, node_id, "READY", {}, provenance(node_id)))
    model.observe_edge(
        WorldEdge(
            "edge:api-worker",
            "service:api",
            "service:worker",
            EdgeKind.DEPENDS_ON,
            provenance("edge-api-worker"),
            confidence=0.9,
        )
    )
    model.observe_edge(
        WorldEdge(
            "edge:worker-db",
            "service:worker",
            "service:db",
            EdgeKind.DEPENDS_ON,
            provenance("edge-worker-db"),
            confidence=0.9,
        )
    )
    return model


class SemanticObservationNormalizerTests(unittest.TestCase):
    def test_normalizes_otel_style_fields_deterministically(self):
        normalizer = SemanticObservationNormalizer()
        record = {
            "kind": "trace",
            "service.name": "service:api",
            "timestamp": "2026-08-31T20:20:00+00:00",
            "name": "http.server.error",
            "severity": 0.8,
            "trace.id": "trace-1",
            "span.id": "span-1",
            "proof_ref": "trace:1",
            "http.status_code": 503,
        }
        first = normalizer.normalize(record)
        second = normalizer.normalize(record)
        self.assertEqual(first.observation_id, second.observation_id)
        self.assertEqual(first.signal_kind, SignalKind.TRACE)
        self.assertEqual(first.target_id, "service:api")
        self.assertEqual(first.trace_id, "trace-1")
        self.assertEqual(first.attributes["http.status_code"], 503)

    def test_missing_proof_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "proof_refs"):
            SemanticObservationNormalizer().normalize(
                {
                    "kind": "event",
                    "target_id": "service:api",
                    "timestamp": NOW,
                    "fingerprint": "x",
                }
            )


class AdaptiveBaselineDetectorTests(unittest.TestCase):
    def test_robust_baseline_detects_outlier(self):
        detector = AdaptiveBaselineDetector(minimum_samples=5, z_threshold=3.5)
        result = detector.assess([100, 101, 99, 100, 102, 98], 140)
        self.assertTrue(result.anomalous)
        self.assertGreater(result.robust_z, 3.5)

    def test_insufficient_samples_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "insufficient"):
            AdaptiveBaselineDetector().assess([1, 2, 3], 4)


class IncidentCorrelatorTests(unittest.TestCase):
    def observation(self, oid, target, fingerprint, seconds, *, trace=None, change=None):
        return NormalizedObservation(
            observation_id=oid,
            source="test",
            signal_kind=SignalKind.EVENT,
            target_id=target,
            observed_at=f"2026-08-31T20:20:{seconds:02d}+00:00",
            fingerprint=fingerprint,
            severity=0.7,
            proof_refs=(f"proof:{oid}",),
            trace_id=trace,
            change_ref=change,
        )

    def test_deduplicates_replays_and_groups_related_signals(self):
        a = self.observation("a", "service:api", "http-503", 1, trace="t1")
        b = self.observation("b", "service:worker", "worker-timeout", 2, trace="t1")
        clusters = IncidentCorrelator(window_seconds=30).cluster((a, a, b))
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].observation_ids, ("a", "b"))

    def test_conflicting_replay_fails_closed(self):
        a = self.observation("a", "service:api", "http-503", 1)
        changed = NormalizedObservation(**{**a.__dict__, "severity": 0.9})
        with self.assertRaisesRegex(ValueError, "conflicting observation replay"):
            IncidentCorrelator().cluster((a, changed))


class MultiWindowSLOGuardTests(unittest.TestCase):
    def test_fast_burn_requires_multi_window_confirmation(self):
        state = MultiWindowSLOGuard().evaluate(
            "service:api",
            (
                SLOWindowSample(5, 1000, 100, 0.99, "slo:5"),
                SLOWindowSample(60, 10000, 200, 0.99, "slo:60"),
            ),
            fast_burn_threshold=6.0,
        )
        self.assertEqual(state.disposition, "FAST_BURN_HOLD_RELEASE")
        self.assertGreaterEqual(state.max_burn_rate, 10.0)

    def test_single_window_burn_only_watches(self):
        state = MultiWindowSLOGuard().evaluate(
            "service:api",
            (
                SLOWindowSample(5, 1000, 20, 0.99, "slo:5"),
                SLOWindowSample(60, 10000, 20, 0.99, "slo:60"),
            ),
        )
        self.assertEqual(state.disposition, "WATCH")


class SentinelObservabilityCausalFabricTests(unittest.TestCase):
    def test_topology_and_change_evidence_rank_probable_origin_without_causal_claim(self):
        model = world()
        fabric = SentinelObservabilityCausalFabric(model)
        assessment = fabric.assess(
            (
                {
                    "kind": "change",
                    "target_id": "service:db",
                    "timestamp": "2026-08-31T20:20:00+00:00",
                    "fingerprint": "deploy-db-v2",
                    "severity": 0.8,
                    "change_ref": "deploy-42",
                    "proof_ref": "deploy:42",
                },
                {
                    "kind": "event",
                    "target_id": "service:worker",
                    "timestamp": "2026-08-31T20:20:10+00:00",
                    "fingerprint": "worker-timeout",
                    "severity": 0.9,
                    "change_ref": "deploy-42",
                    "proof_ref": "worker:timeout",
                },
                {
                    "kind": "trace",
                    "target_id": "service:api",
                    "timestamp": "2026-08-31T20:20:20+00:00",
                    "fingerprint": "http-503",
                    "severity": 0.9,
                    "trace_id": "trace-incident",
                    "proof_ref": "trace:incident",
                },
            )
        )
        self.assertEqual(len(assessment.clusters), 1)
        ranking = assessment.origin_rankings[assessment.clusters[0].incident_id]
        self.assertEqual(ranking[0].target_id, "service:db")
        self.assertFalse(ranking[0].causal_claim)
        self.assertGreater(ranking[0].topology_coverage, 0.5)

    def test_topology_without_change_or_trace_anchor_does_not_overgroup(self):
        assessment = SentinelObservabilityCausalFabric(world()).assess(
            (
                {
                    "kind": "event",
                    "target_id": "service:db",
                    "timestamp": "2026-08-31T20:20:00+00:00",
                    "fingerprint": "db-noise",
                    "severity": 0.3,
                    "proof_ref": "db:noise",
                },
                {
                    "kind": "event",
                    "target_id": "service:api",
                    "timestamp": "2026-08-31T20:20:05+00:00",
                    "fingerprint": "api-noise",
                    "severity": 0.3,
                    "proof_ref": "api:noise",
                },
            )
        )
        self.assertEqual(len(assessment.clusters), 2)

    def test_remediation_bridge_emits_a1_internal_effect_free_actions(self):
        model = world()
        assessment = SentinelObservabilityCausalFabric(model).assess(
            (
                {
                    "kind": "event",
                    "target_id": "service:api",
                    "timestamp": NOW,
                    "fingerprint": "http-503",
                    "severity": 0.9,
                    "proof_ref": "incident:1",
                },
            )
        )
        self.assertTrue(assessment.remediation_actions)
        action = assessment.remediation_actions[0]
        self.assertEqual(action.authority_ceiling.value, "A1_INTERNAL")
        self.assertFalse(action.external_effect)
        self.assertIn("Falsify probable origin", action.objective)

    def test_assessment_receipt_is_deterministic(self):
        observations = (
            {
                "kind": "event",
                "target_id": "service:api",
                "timestamp": NOW,
                "fingerprint": "http-503",
                "severity": 0.9,
                "proof_ref": "incident:1",
            },
        )
        first = SentinelObservabilityCausalFabric(world()).assess(observations)
        second = SentinelObservabilityCausalFabric(world()).assess(observations)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertIn("not verified causality", first.truth_boundary)

    def test_slo_states_integrate_without_authorizing_effects(self):
        assessment = SentinelObservabilityCausalFabric(world()).assess(
            (
                {
                    "kind": "health",
                    "target_id": "service:api",
                    "timestamp": NOW,
                    "fingerprint": "latency-regression",
                    "severity": 0.6,
                    "proof_ref": "health:1",
                },
            ),
            slo_samples={
                "service:api": (
                    SLOWindowSample(5, 1000, 80, 0.99, "slo:short"),
                    SLOWindowSample(60, 10000, 300, 0.99, "slo:long"),
                )
            },
        )
        self.assertEqual(assessment.slo_states[0].disposition, "FAST_BURN_HOLD_RELEASE")
        self.assertFalse(assessment.external_effect)


if __name__ == "__main__":
    unittest.main()
