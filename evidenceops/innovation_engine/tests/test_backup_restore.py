from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from evidenceops.innovation_engine.registry import InnovationRegistry


class InnovationRegistryBackupRestoreTests(unittest.TestCase):
    def test_backup_restore_preserves_lanes_events_and_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = InnovationRegistry(root / "primary.db")
            primary.upsert_lane(
                "LANE-001", "Test lane", "Prove backup recovery", "READY",
                99, "Run recovery drill", "LOCAL_TEST",
            )
            transition = primary.transition(
                "LANE-001", "ACTIVE", ["bounded_test"], "Start deterministic drill"
            )

            receipt = primary.backup(root / "backup.db")
            self.assertEqual(receipt.integrity_check, "ok")
            self.assertTrue(receipt.chain_verified)
            self.assertEqual(receipt.lane_count, 1)
            self.assertEqual(receipt.event_count, 1)

            restored = InnovationRegistry.restore(
                root / "backup.db", root / "restored.db", receipt.database_sha256
            )
            self.assertTrue(restored.verify_chain())
            with restored._connect() as connection:
                lane = connection.execute(
                    "SELECT state FROM lanes WHERE lane_id='LANE-001'"
                ).fetchone()
                event = connection.execute(
                    "SELECT receipt_hash FROM events WHERE lane_id='LANE-001'"
                ).fetchone()
            self.assertEqual(lane["state"], "ACTIVE")
            self.assertEqual(event["receipt_hash"], transition.receipt_hash)

    def test_restore_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = InnovationRegistry(root / "primary.db")
            registry.upsert_lane(
                "LANE-001", "Test lane", "Prove backup recovery", "READY",
                99, "Run recovery drill", "LOCAL_TEST",
            )
            registry.backup(root / "backup.db")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                InnovationRegistry.restore(
                    root / "backup.db", root / "restored.db", "0" * 64
                )

    def test_restore_rejects_tampered_receipt_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = InnovationRegistry(root / "primary.db")
            registry.upsert_lane(
                "LANE-001", "Test lane", "Prove backup recovery", "READY",
                99, "Run recovery drill", "LOCAL_TEST",
            )
            registry.transition("LANE-001", "ACTIVE", [], "Start")
            registry.backup(root / "backup.db")
            with sqlite3.connect(root / "backup.db") as connection:
                connection.execute(
                    "UPDATE events SET reason='tampered' WHERE lane_id='LANE-001'"
                )
            tampered_sha = InnovationRegistry._file_sha256(root / "backup.db")
            with self.assertRaisesRegex(RuntimeError, "chain verification failed"):
                InnovationRegistry.restore(
                    root / "backup.db", root / "restored.db", tampered_sha
                )


if __name__ == "__main__":
    unittest.main()
