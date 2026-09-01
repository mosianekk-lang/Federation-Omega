import unittest

from federation.sentinel_omega.observation_ingress import (
    GitHubWorkflowRunAdapter,
    HeartbeatObservationAdapter,
    ObservationIngressBatch,
    ProjectionDriftObservationAdapter,
    QueueObservationAdapter,
)
from federation.sentinel_omega.observability_causal_fabric import SignalKind


class GitHubWorkflowRunAdapterTests(unittest.TestCase):
    def test_failed_run_becomes_high_severity_event(self):
        item = GitHubWorkflowRunAdapter().adapt(
            {
                "id": 123,
                "name": "Federation Omega Airlock",
                "status": "completed",
                "conclusion": "failure",
                "updated_at": "2026-08-31T20:00:00Z",
                "head_sha": "abc123",
                "event": "pull_request",
            },
            proof_ref="github:run:123",
        )
        self.assertEqual(item.signal_kind, SignalKind.EVENT)
        self.assertGreater(item.severity, 0.9)
        self.assertEqual(item.change_ref, "abc123")
        self.assertIn("FAILURE", item.fingerprint)

    def test_successful_run_is_low_severity_health(self):
        item = GitHubWorkflowRunAdapter().adapt(
            {
                "id": 124,
                "name": "Bubbles Command Bus",
                "status": "completed",
                "conclusion": "success",
                "updated_at": "2026-08-31T20:01:00+00:00",
            },
            proof_ref="github:run:124",
        )
        self.assertEqual(item.signal_kind, SignalKind.HEALTH)
        self.assertLess(item.severity, 0.1)

    def test_missing_provider_proof_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "proof_ref"):
            GitHubWorkflowRunAdapter().adapt(
                {"id": 1, "name": "x", "status": "completed", "conclusion": "success", "updated_at": "2026-08-31T20:00:00Z"},
                proof_ref="",
            )


class HeartbeatObservationAdapterTests(unittest.TestCase):
    def test_fatal_heartbeat_becomes_event(self):
        item = HeartbeatObservationAdapter().adapt(
            {
                "heartbeat_id": "hb-1",
                "checkedAt": "2026-08-31T20:00:00Z",
                "status": "RUN_FATAL",
                "version": "1",
                "scriptId": "script-1",
            },
            target_id="sentinel:apps-script",
            proof_ref="sheet:heartbeat:1",
        )
        self.assertEqual(item.signal_kind, SignalKind.EVENT)
        self.assertGreater(item.severity, 0.9)

    def test_idle_heartbeat_is_healthy(self):
        item = HeartbeatObservationAdapter().adapt(
            {"checkedAt": "2026-08-31T20:00:00Z", "status": "IDLE_EMPTY_QUEUE"},
            target_id="sentinel:apps-script",
            proof_ref="sheet:heartbeat:2",
        )
        self.assertEqual(item.signal_kind, SignalKind.HEALTH)
        self.assertLess(item.severity, 0.1)


class QueueObservationAdapterTests(unittest.TestCase):
    def test_stale_pending_queue_item_escalates(self):
        item = QueueObservationAdapter().adapt(
            {
                "Command_ID": "cmd-1",
                "Status": "PENDING",
                "Updated_At": "2026-08-31T18:00:00Z",
                "Retry_Count": 2,
            },
            queue_id="sentinel",
            proof_ref="sheet:queue:1",
            now="2026-08-31T20:00:00Z",
        )
        self.assertEqual(item.signal_kind, SignalKind.QUEUE)
        self.assertGreaterEqual(item.severity, 0.9)
        self.assertEqual(item.attributes["retry_count"], 2)

    def test_completed_queue_item_is_low_severity(self):
        item = QueueObservationAdapter().adapt(
            {"Command_ID": "cmd-2", "Status": "CLOSED_VERIFIED_GAS", "Updated_At": "2026-08-31T20:00:00Z"},
            queue_id="sentinel",
            proof_ref="sheet:queue:2",
            now="2026-08-31T20:01:00Z",
        )
        self.assertLess(item.severity, 0.1)

    def test_executed_queue_item_is_low_severity(self):
        item = QueueObservationAdapter().adapt(
            {"command_id": "cmd-3", "status": "EXECUTED", "updated_at": "2026-09-01T04:29:45Z"},
            queue_id="architron-command",
            proof_ref="sheet:Command_Queue:2",
            now="2026-09-01T16:49:44Z",
        )
        self.assertEqual(item.attributes["status"], "EXECUTED")
        self.assertLess(item.severity, 0.1)


class ProjectionDriftObservationAdapterTests(unittest.TestCase):
    def test_drift_is_high_severity_event(self):
        item = ProjectionDriftObservationAdapter().adapt(
            system_id="BUBBLES",
            observed_ref="oldsha",
            expected_ref="newsha",
            observed_at="2026-08-31T20:00:00Z",
            proof_ref="sync:row:1",
        )
        self.assertEqual(item.signal_kind, SignalKind.EVENT)
        self.assertTrue(item.attributes["drifted"])
        self.assertGreater(item.severity, 0.8)

    def test_matching_projection_is_low_severity_proof(self):
        item = ProjectionDriftObservationAdapter().adapt(
            system_id="BUBBLES",
            observed_ref="sha",
            expected_ref="sha",
            observed_at="2026-08-31T20:00:00Z",
            proof_ref="sync:row:2",
        )
        self.assertEqual(item.signal_kind, SignalKind.PROOF)
        self.assertFalse(item.attributes["drifted"])


class ObservationIngressBatchTests(unittest.TestCase):
    def test_exact_replay_deduplicates(self):
        adapter = ProjectionDriftObservationAdapter()
        item = adapter.adapt(
            system_id="FEDERATION",
            observed_ref="sha",
            expected_ref="sha",
            observed_at="2026-08-31T20:00:00Z",
            proof_ref="sync:row:3",
        )
        batch = ObservationIngressBatch.collect((item, item))
        self.assertEqual(len(batch), 1)

    def test_conflicting_replay_fails_closed(self):
        adapter = ProjectionDriftObservationAdapter()
        one = adapter.adapt(
            system_id="FEDERATION",
            observed_ref="sha1",
            expected_ref="sha2",
            observed_at="2026-08-31T20:00:00Z",
            proof_ref="sync:row:4",
        )
        two = type(one)(**{**one.__dict__, "severity": 0.2})
        with self.assertRaisesRegex(ValueError, "conflicting ingress observation"):
            ObservationIngressBatch.collect((one, two))


if __name__ == "__main__":
    unittest.main()

