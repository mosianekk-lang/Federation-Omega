import gc
import sqlite3
import tempfile
import warnings
import unittest
from pathlib import Path

from evidenceops.innovation_engine.registry import InnovationRegistry


class InnovationEngineRegistryTests(unittest.TestCase):
    def make_registry(self, directory: str) -> InnovationRegistry:
        registry = InnovationRegistry(Path(directory) / "innovation.db")
        registry.upsert_lane(
            lane_id="LANE-TEST",
            title="Test lane",
            objective="Prove deterministic registry behaviour",
            state="READY",
            priority=100,
            next_action="Run test",
            proof_state="SCAFFOLD",
        )
        return registry

    def test_promotion_fails_closed_without_required_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = self.make_registry(directory)
            with self.assertRaisesRegex(ValueError, "Proof gate failed"):
                registry.transition(
                    "LANE-TEST",
                    "PILOT_APPROVED",
                    ["hypothesis"],
                    "insufficient proof",
                )

    def test_transition_creates_verifiable_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = self.make_registry(directory)
            first = registry.transition(
                "LANE-TEST", "ACTIVE", ["owner_authority"], "start bounded work"
            )
            second = registry.transition(
                "LANE-TEST", "CHECKPOINTED", ["artifact_hash"], "preserve continuity"
            )

            self.assertIsNone(first.previous_hash)
            self.assertEqual(second.previous_hash, first.receipt_hash)
            self.assertTrue(registry.verify_chain())

    def test_pilot_gate_passes_with_complete_proof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = self.make_registry(directory)
            receipt = registry.transition(
                "LANE-TEST",
                "PILOT_APPROVED",
                ["hypothesis", "success_metrics", "bounded_test", "rollback_plan"],
                "all deterministic pilot gates passed",
            )
            self.assertEqual(receipt.target_state, "PILOT_APPROVED")
            self.assertTrue(registry.verify_chain())

    def test_connections_close_across_registry_backup_and_restore(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            with tempfile.TemporaryDirectory() as directory:
                registry = self.make_registry(directory)
                registry.transition(
                    "LANE-TEST", "ACTIVE", ["owner_authority"], "exercise connection lifecycle"
                )
                backup = Path(directory) / "backup.db"
                receipt = registry.backup(backup)
                restored = InnovationRegistry.restore(
                    backup, Path(directory) / "restored.db", receipt.database_sha256
                )
                self.assertTrue(restored.verify_chain())
                with registry._connect() as connection:
                    self.assertEqual(1, connection.execute("SELECT 1").fetchone()[0])
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")
                del restored
                del registry
                gc.collect()
            unclosed = [
                warning for warning in caught
                if issubclass(warning.category, ResourceWarning)
                and "unclosed database" in str(warning.message)
            ]
        self.assertEqual([], unclosed)


if __name__ == "__main__":
    unittest.main()
