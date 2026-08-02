from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidenceops.capability_heartbeat.engine import HeartbeatError
from evidenceops.capability_heartbeat.system import EvidenceOpsHeartbeatSystem


ROOT = Path(__file__).resolve().parents[3]
SURFACES = ROOT / "evidenceops/capability_heartbeat/surface_registry.json"


class HeartbeatSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.system = EvidenceOpsHeartbeatSystem(
            Path(self.temp.name) / "heartbeat.db", repository_root=ROOT
        )
        self.registry = self.system.load_surface_registry(SURFACES)
        self.index = self.system.index_surfaces(
            self.registry, observed_at="2026-08-02T12:00:00+00:00"
        )

    def tearDown(self):
        self.system.close()
        self.temp.cleanup()

    def event(self, **changes):
        value = {
            "schema": "EVIDENCEOPS-CHAT-TURN-EVENT-1",
            "event_id": "EVENT-ONE",
            "chat_id": "CHAT-ONE",
            "turn_id": "TURN-ONE",
            "surface_id": "chatgpt",
            "sequence": 1,
            "emitted_at": "2026-08-02T12:00:00+00:00",
            "privacy_tier": "P1",
            "task_summary": "Resolve the integration issue",
            "blockers": ["provider adapter is missing"],
            "risk_flags": [],
            "requirements": [{
                "requirement_id": "TURN-ROUTE",
                "tags": ["discover", "reuse", "verify"],
                "minimum_proof": "TESTED", "maximum_authority": "A1",
                "baseline_score": 0.2, "baseline_safety": 0.8,
                "improvement_threshold": 0.05, "effectful_permit": False,
            }],
        }
        value.update(changes)
        return value

    def test_all_documented_surfaces_receive_nodes_and_gap_cases(self):
        self.assertEqual(self.index["surface_count"], len(self.registry["surfaces"]))
        self.assertEqual(len({x["node_id"] for x in self.index["surfaces"]}), self.index["surface_count"])
        remediation = self.system.remediation_cycle(observed_at="2026-08-02T12:01:00+00:00")
        self.assertEqual(remediation["open_case_count"], self.index["surface_count"])
        self.assertFalse(remediation["bypass_attempted"])
        self.assertTrue(all(case["next_action"] for case in remediation["cases"]))

    def test_turn_is_atomic_idempotent_and_returns_assistance(self):
        first = self.system.ingest_turn(self.event())
        second = self.system.ingest_turn(self.event())
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["response"]["kind"], "ACK_WITH_ASSISTANCE")
        self.assertTrue(first["response"]["capability_decisions"])
        self.assertEqual(len(self.system.outbox("CHAT-ONE")), 1)

    def test_replay_sequence_is_rejected_and_gap_is_sync_pending(self):
        self.system.ingest_turn(self.event())
        with self.assertRaises(HeartbeatError):
            self.system.ingest_turn(self.event(event_id="EVENT-REPLAY", turn_id="TURN-REPLAY"))
        gap = self.system.ingest_turn(self.event(
            event_id="EVENT-GAP", turn_id="TURN-GAP", sequence=3,
            emitted_at="2026-08-02T12:02:00+00:00",
        ))
        self.assertEqual(gap["node_state"], "NODE_SYNC_PENDING")
        self.assertEqual(gap["response"]["sequence_gap"], 1)

    def test_p2_event_projects_chat_and_task_details(self):
        result = self.system.ingest_turn(self.event(privacy_tier="P2"))
        self.assertTrue(result["chat_ref"].startswith("sha256:"))
        row = self.system.conn.execute("SELECT payload_json FROM turn_events").fetchone()
        payload = json.loads(row["payload_json"])
        self.assertIsNone(payload["task_summary"])
        self.assertNotIn("CHAT-ONE", row["payload_json"])

    def test_stale_reconciliation_does_not_infer_liveness(self):
        self.system.ingest_turn(self.event())
        report = self.system.reconcile(observed_at="2026-08-02T13:00:00+00:00")
        self.assertEqual(report["stale_count"], 1)
        self.assertEqual(report["active_count"], 0)

    def test_kimmie_seed_requires_pre_before_post_and_hashes_private_results(self):
        seed = self.system.seed_connector(
            chat_id="CHAT-ONE", connector_id="google-drive", privacy_tier="P2",
            created_at="2026-08-02T12:00:00+00:00",
        )
        with self.assertRaises(HeartbeatError):
            self.system.record_connector_cycle(
                seed_id=seed["seed_id"], operation_id="OP-ONE", phase="POST",
                capability="drive-search", status="SUCCESS",
                result_summary="private result", created_at="2026-08-02T12:00:01+00:00",
            )
        self.system.record_connector_cycle(
            seed_id=seed["seed_id"], operation_id="OP-ONE", phase="PRE",
            capability="drive-search", status="AUTHORISED",
            created_at="2026-08-02T12:00:01+00:00",
        )
        post = self.system.record_connector_cycle(
            seed_id=seed["seed_id"], operation_id="OP-ONE", phase="POST",
            capability="drive-search", status="SUCCESS", result_summary="private result",
            created_at="2026-08-02T12:00:02+00:00",
        )
        self.assertEqual(post["state"], "POST_RECEIPT_BOUND")
        self.assertIsNone(post["result_summary"])
        self.assertTrue(post["result_ref"].startswith("sha256:"))

    def test_unindexed_or_unbound_surface_cannot_submit_turn(self):
        with self.assertRaises(HeartbeatError):
            self.system.ingest_turn(self.event(surface_id="canva"))


if __name__ == "__main__":
    unittest.main()
