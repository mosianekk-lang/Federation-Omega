from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ops.architron_local_semantic_canary import SemanticCanaryStore


class ArchitronBridgeCanaryTests(unittest.TestCase):
    def test_event_queue_worker_target_readback_audit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SemanticCanaryStore(Path(tmp) / "bridge.sqlite")
            try:
                self.assertTrue(store.enqueue("EVT-1", "demo.marker", "verified"))
                receipt = store.run_one("EVT-1")
                self.assertEqual("LOCAL_SEMANTIC_VERIFIED", receipt.execution_state)
                self.assertEqual("verified", receipt.target_readback)
                self.assertEqual("verified", store.target_value("demo.marker"))
                self.assertEqual(64, len(receipt.audit_sha256))
                self.assertFalse(receipt.idempotent_replay)
            finally:
                store.close()

    def test_duplicate_event_is_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SemanticCanaryStore(Path(tmp) / "bridge.sqlite")
            try:
                self.assertTrue(store.enqueue("EVT-2", "demo.marker", "one"))
                first = store.run_one("EVT-2")
                self.assertFalse(store.enqueue("EVT-2", "demo.marker", "two"))
                replay = store.run_one("EVT-2")
                self.assertEqual(first.execution_id, replay.execution_id)
                self.assertTrue(replay.idempotent_replay)
                self.assertEqual("one", store.target_value("demo.marker"))
            finally:
                store.close()

    def test_retryable_failure_recovers_without_duplicate_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SemanticCanaryStore(Path(tmp) / "bridge.sqlite")
            try:
                store.enqueue("EVT-3", "demo.retry", "recovered", fail_once=True)
                with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_RETRYABLE_FAILURE"):
                    store.run_one("EVT-3")
                self.assertIsNone(store.target_value("demo.retry"))
                receipt = store.run_one("EVT-3")
                self.assertTrue(receipt.recovered_after_failure)
                self.assertEqual(2, receipt.attempts)
                self.assertEqual("recovered", store.target_value("demo.retry"))
            finally:
                store.close()

    def test_wrong_target_readback_fails_semantically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SemanticCanaryStore(Path(tmp) / "bridge.sqlite")
            try:
                store.enqueue("EVT-4", "demo.readback", "expected")
                with self.assertRaisesRegex(RuntimeError, "SEMANTIC_READBACK_MISMATCH"):
                    store.run_one("EVT-4", readback=lambda _key: "wrong")
            finally:
                store.close()

    def test_receipt_truth_boundary_does_not_claim_provider_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SemanticCanaryStore(Path(tmp) / "bridge.sqlite")
            try:
                store.enqueue("EVT-5", "demo.truth", "safe")
                receipt = store.run_one("EVT-5")
                self.assertIn("does not prove Google Apps Script", receipt.truth_boundary)
                self.assertNotEqual("PROVIDER_VERIFIED", receipt.execution_state)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
