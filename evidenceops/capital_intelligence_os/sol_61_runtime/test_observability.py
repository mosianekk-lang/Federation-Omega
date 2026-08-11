from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from observability import ObservabilityFabric, ProofRecord, SLO, TraceSpan


class ObservabilityFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fabric = ObservabilityFabric(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_trace_correlation_and_restart(self) -> None:
        spans = [
            TraceSpan("t1", "s1", None, "gateway", "request", 1000, 20, "OK"),
            TraceSpan("t1", "s2", "s1", "provider", "deploy", 1020, 30, "ERROR"),
            TraceSpan("t1", "s3", "s2", "readback", "verify", 1050, 10, "ERROR"),
        ]
        for span in spans:
            self.fabric.record_span(span)
        correlation = self.fabric.correlate_trace_failures("t1")
        self.assertEqual(correlation["root_candidate"], "s2")
        self.assertEqual(correlation["downstream_failures"], ["s3"])
        restarted = ObservabilityFabric(self.root)
        self.assertTrue(restarted.verify_chain())
        self.assertEqual(restarted.correlate_trace_failures("t1"), correlation)

    def test_slo_and_anomaly(self) -> None:
        self.fabric.register_slo(SLO("latency", "gateway", "latency_ms", 100, "LTE", 5))
        for value in [50, 55, 60, 58, 57]:
            self.fabric.record_metric("latency_ms", value)
        self.assertTrue(self.fabric.evaluate_slo("latency")["pass"])
        anomaly = self.fabric.detect_anomaly("latency_ms", 180)
        self.assertTrue(anomaly["anomaly"])

    def test_proof_freshness_and_false_completion(self) -> None:
        self.fabric.register_proof(ProofRecord("p1", "deploy", 100, 50, "a" * 64))
        self.assertTrue(self.fabric.proof_freshness("p1", 120)["fresh"])
        result = self.fabric.detect_false_completion("VERIFIED", ["p1", "p2"], 200)
        self.assertTrue(result["false_completion"])
        self.assertEqual(result["missing_proofs"], ["p2"])
        self.assertEqual(result["stale_proofs"], ["p1"])

    def test_incident_deduplication(self) -> None:
        signal = [{"metric": "error_rate", "value": 0.4}]
        first = self.fabric.form_incident(title="Provider failure", severity="SEV2", signals=signal, correlation={"root": "provider"})
        second = self.fabric.form_incident(title="Provider failure", severity="SEV2", signals=signal, correlation={"root": "provider"})
        self.assertEqual(first["incident_id"], second["incident_id"])
        self.assertEqual(len(self.fabric.incidents), 1)


if __name__ == "__main__":
    unittest.main()
