from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASE_MANIFEST = ROOT / "config" / "kim-dataverse-schema-manifest-v1.json"
OMEGA47_MANIFEST = ROOT / "config" / "kim-dataverse-schema-manifest-omega47-v1.json"
CONSUMER_MAP = ROOT / "config" / "kim-dataverse-consumer-map-v1.json"


class ChatBridgeOmega47KDVSchemaTests(unittest.TestCase):
    def test_successor_manifest_extends_65_sheet_baseline_to_70(self) -> None:
        base = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
        successor = json.loads(OMEGA47_MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(len(base["sheet_summaries"]), 65)
        self.assertEqual(successor["base_manifest"]["base_sheet_count"], 65)
        self.assertEqual(successor["current_sheet_count"], 70)
        self.assertEqual(successor["private_registry_state"], "70_OF_70_BOUND")

        expected = {
            "CHATBRIDGE_CONTEXT_GUARD": (20, "guard_event_id"),
            "CHATBRIDGE_CONTEXT_CHECKPOINTS": (24, "checkpoint_id"),
            "CHATBRIDGE_LEARNING_EVENTS": (24, "learning_event_id"),
            "CHATBRIDGE_PLAYBOOK_RULES": (22, "rule_id"),
            "CHATBRIDGE_PLAYBOOK_RELEASES": (18, "release_id"),
        }
        additions = {
            item["sheet_name"]: item
            for item in successor["additional_sheet_summaries"]
        }
        self.assertEqual(set(additions), set(expected))

        hashes = set()
        for name, (field_count, key) in expected.items():
            item = additions[name]
            self.assertEqual(item["field_count"], field_count)
            self.assertEqual(item["candidate_primary_key"], key)
            digest = item["structural_schema_sha256"]
            self.assertRegex(digest, re.compile(r"^[0-9a-f]{64}$"))
            hashes.add(digest)
        self.assertEqual(len(hashes), 5)

    def test_chatbridge_restore_consumer_cannot_drop_omega47_controls(self) -> None:
        contract = json.loads(CONSUMER_MAP.read_text(encoding="utf-8"))
        consumers = {
            item["consumer"]: item
            for item in contract["consumers"]
        }

        restore = consumers["ChatBridge restore"]
        for table in (
            "CHATBRIDGE_CONTEXT_GUARD",
            "CHATBRIDGE_CONTEXT_CHECKPOINTS",
            "CHATBRIDGE_PLAYBOOK_RULES",
            "CHATBRIDGE_PLAYBOOK_RELEASES",
        ):
            self.assertIn(table, restore["reads"])
        joined = " ".join(restore["must_reconcile"]).casefold()
        self.assertIn("guard", joined)
        self.assertIn("playbook", joined)
        self.assertIn("exact namespace", joined)

    def test_empirical_learning_consumer_preserves_proof_and_privacy_gates(self) -> None:
        contract = json.loads(CONSUMER_MAP.read_text(encoding="utf-8"))
        consumers = {
            item["consumer"]: item
            for item in contract["consumers"]
        }
        learning = consumers["ChatBridge empirical learning and playbook compiler"]
        self.assertIn("CHATBRIDGE_LEARNING_EVENTS", learning["reads"])
        controls = " ".join(learning["must_reconcile"]).casefold()
        self.assertIn("privacy", controls)
        self.assertIn("independent support", controls)
        self.assertIn("provider or reproduced-canary", controls)
        self.assertIn("zero automatic", controls)
        self.assertIn("sensitive-data leakage", learning["risk"])


if __name__ == "__main__":
    unittest.main()
