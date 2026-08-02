from __future__ import annotations

import unittest

from evidenceops.capability_heartbeat.bible_federation import BibleFederation
from evidenceops.capability_heartbeat.engine import CapabilityHeartbeatEngine, HeartbeatError


class BibleFederationTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "schema": "EVIDENCEOPS-BIBLE-NODE-1",
            "node_id": "NODE-EVIDENCEOPS-PARENT",
            "parent_node_id": "CENTRAL-MASTER",
            "contract_version": "MB-HB-1.0",
            "branch_version": 2,
            "privacy_tier": "P1",
            "ttl_seconds": 300,
            "max_hops": 3,
            "active_workflow_ids": ["CHAT-A"],
            "authorized_child_patterns": ["NODE-EVIDENCEOPS-*"],
        }
        self.federation = BibleFederation(self.contract)
        self.heartbeat = self.federation.make_heartbeat(
            "report:abc123", emitted_at="2026-08-02T12:00:00+00:00"
        )

    def test_authorized_child_inherits_verified_contract(self):
        child = self.federation.make_child_genesis("NODE-EVIDENCEOPS-CHILD", self.heartbeat)
        self.assertEqual(child["parent_node_id"], self.contract["node_id"])
        self.assertFalse(child["effectful_execution_inherited"])
        self.assertIn("READ_BACK_REGISTRY_RECEIPT", child["required_startup_sequence"])

    def test_unauthorized_child_is_rejected(self):
        with self.assertRaises(HeartbeatError):
            self.federation.make_child_genesis("NODE-ROGUE-CHILD", self.heartbeat)

    def test_propagation_loop_is_rejected(self):
        with self.assertRaises(HeartbeatError):
            self.federation.make_child_genesis("CENTRAL-MASTER", self.heartbeat)

    def test_private_workflow_identifiers_are_hashed(self):
        private = {**self.contract, "privacy_tier": "P3"}
        envelope = BibleFederation(private).make_heartbeat(
            "report:abc123", emitted_at="2026-08-02T12:00:00+00:00"
        )
        self.assertNotIn("CHAT-A", envelope["active_workflow_refs"])
        self.assertTrue(envelope["active_workflow_refs"][0].startswith("sha256:"))

    def test_reconciliation_distinguishes_active_stale_missing_and_unregistered(self):
        stale = self.federation.make_heartbeat(
            "report:stale", emitted_at="2026-08-02T11:00:00+00:00"
        )
        rogue_contract = {**self.contract, "node_id": "NODE-EVIDENCEOPS-ROGUE"}
        rogue = BibleFederation(rogue_contract).make_heartbeat(
            "report:rogue", emitted_at="2026-08-02T12:00:00+00:00"
        )
        result = BibleFederation.reconcile(
            {"NODE-EVIDENCEOPS-PARENT", "NODE-EVIDENCEOPS-MISSING"},
            [stale, rogue],
            observed_at="2026-08-02T12:00:00+00:00",
        )
        states = {item["node_id"]: item["state"] for item in result["nodes"]}
        self.assertEqual(states["NODE-EVIDENCEOPS-PARENT"], "NODE_STALE")
        self.assertEqual(states["NODE-EVIDENCEOPS-MISSING"], "NODE_SYNC_PENDING")
        self.assertEqual(result["quarantined_unregistered_nodes"], ["NODE-EVIDENCEOPS-ROGUE"])

    def test_hash_tampering_is_rejected(self):
        changed = {**self.heartbeat, "status": "NODE_ARCHIVED"}
        with self.assertRaises(HeartbeatError):
            BibleFederation.verify_heartbeat(changed)

    def test_older_heartbeat_replay_is_rejected(self):
        newer = self.federation.make_heartbeat(
            "report:newer", emitted_at="2026-08-02T12:02:00+00:00"
        )
        result = BibleFederation.reconcile(
            {"NODE-EVIDENCEOPS-PARENT"},
            [newer, self.heartbeat],
            observed_at="2026-08-02T12:03:00+00:00",
        )
        self.assertEqual(result["rejected_replay_heartbeats"], [self.heartbeat["heartbeat_sha256"]])
        self.assertEqual(result["active_node_count"], 1)

    def test_current_report_contains_bible_node_envelope(self):
        root = __import__("pathlib").Path(__file__).resolve().parents[3]
        report = CapabilityHeartbeatEngine(
            root,
            "evidenceops/capability_heartbeat/sources.json",
            "evidenceops/capability_heartbeat/bible_node.json",
        ).run("evidenceops/capability_heartbeat/current_workflow.json")
        self.assertEqual(report["bible_node_heartbeat"]["node_id"], "NODE-EVIDENCEOPS-CAPABILITY-HEARTBEAT")
        self.assertEqual(report["bible_node_heartbeat"]["status"], "NODE_ACTIVE_VERIFIED")
        self.assertFalse(report["bible_node_heartbeat"]["credentials_included"])


if __name__ == "__main__":
    unittest.main()
