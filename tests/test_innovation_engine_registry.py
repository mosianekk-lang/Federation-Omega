import tempfile
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


if __name__ == "__main__":
    unittest.main()
