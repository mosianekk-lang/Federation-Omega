import json
from pathlib import Path
import tempfile
import unittest

from omega_one.telemetry import (
    CloudEvent,
    HashChainedAuditJournal,
    MetricsRegistry,
    TraceContext,
    redact,
)


class TelemetryTests(unittest.TestCase):
    def test_redacts_credentials_and_bounds_payloads(self):
        result = redact({"api_key": "do-not-log", "nested": {"password": "x"}, "body": "z" * 600})
        self.assertEqual(result["api_key"], "[REDACTED]")
        self.assertEqual(result["nested"]["password"], "[REDACTED]")
        self.assertIn("truncated", result["body"])

    def test_trace_context_roundtrip_and_child(self):
        parent = TraceContext.new()
        parsed = TraceContext.parse(parent.traceparent)
        child = parsed.child()
        self.assertEqual(parent.trace_id, child.trace_id)
        self.assertNotEqual(parent.span_id, child.span_id)
        with self.assertRaisesRegex(ValueError, "INVALID_TRACEPARENT"):
            TraceContext.parse("00-" + "0" * 32 + "-" + "0" * 16 + "-01")

    def test_hash_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            journal = HashChainedAuditJournal(path)
            journal.append(CloudEvent.create(event_type="task.ready", subject="T1", data={"token": "no"}))
            journal.append(CloudEvent.create(event_type="task.proven", subject="T1", data={"proof": "ok"}))
            self.assertTrue(journal.verify())
            rows = path.read_text(encoding="utf-8").splitlines()
            row = json.loads(rows[0])
            row["event"]["data"]["proof"] = "tampered"
            rows[0] = json.dumps(row)
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            self.assertFalse(journal.verify())

    def test_metrics_snapshot(self):
        metrics = MetricsRegistry()
        metrics.increment("dispatch")
        metrics.gauge("queue_depth", 4)
        for value in (1, 2, 3, 4):
            metrics.observe("latency_ms", value)
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot["counters"]["dispatch"], 1)
        self.assertEqual(snapshot["gauges"]["queue_depth"], 4)
        self.assertEqual(snapshot["distributions"]["latency_ms"]["count"], 4)


if __name__ == "__main__":
    unittest.main()
