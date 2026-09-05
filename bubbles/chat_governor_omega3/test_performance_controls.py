from __future__ import annotations

import tempfile
import unittest

from bubbles.chat_governor_omega3.performance_controls import (
    FenceRejected,
    FencedLedgerHead,
    HardContextCapsuleError,
    LedgerConflict,
    assess_stream,
    build_hard_context_capsule,
    sign_recovery_snapshot,
    verify_recovery_snapshot,
)


class RecoverySnapshotTests(unittest.TestCase):
    def payload(self):
        return {
            "snapshot_id": "s1",
            "producer_id": "chatgov",
            "mission_id": "m1",
            "generation": 6,
            "created_at": 100.0,
            "expires_at": 200.0,
            "source_epochs": {"github": "abc"},
            "coverage": {"source": True, "provider": True},
            "state": "VERIFIED",
        }

    def test_signed_snapshot_accepts_exact_generation_and_coverage(self):
        signed = sign_recovery_snapshot(self.payload(), key=b"test-key", key_id="k1")
        verdict = verify_recovery_snapshot(signed, key=b"test-key", now=150.0, expected_generation=6, required_coverage=("source", "provider"))
        self.assertEqual(verdict["decision"], "ACCEPT")

    def test_stale_or_wrong_generation_rejected(self):
        signed = sign_recovery_snapshot(self.payload(), key=b"test-key", key_id="k1")
        stale = verify_recovery_snapshot(signed, key=b"test-key", now=200.0, expected_generation=7)
        self.assertEqual(stale["decision"], "REJECT")
        self.assertIn("SNAPSHOT_STALE", stale["issues"])
        self.assertIn("GENERATION_MISMATCH", stale["issues"])

    def test_tamper_rejected(self):
        signed = sign_recovery_snapshot(self.payload(), key=b"test-key", key_id="k1")
        signed["source_epochs"] = {"github": "evil"}
        verdict = verify_recovery_snapshot(signed, key=b"test-key", now=150.0)
        self.assertEqual(verdict["decision"], "REJECT")
        self.assertIn("SIGNATURE_INVALID", verdict["issues"])


class LedgerHeadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        tmp.close()
        self.ledger = FencedLedgerHead(tmp.name)

    def test_head_is_o1_and_chain_verifies(self):
        first = self.ledger.append(task_id="t", generation=1, slot="a", fence=1, payload={"x": 1})
        second = self.ledger.append(task_id="t", generation=1, slot="b", fence=1, payload={"x": 2}, expected_head_hash=first["receipt_hash"])
        self.assertEqual(self.ledger.head("t")["receipt_hash"], second["receipt_hash"])
        self.assertEqual(self.ledger.verify_chain("t")["decision"], "VERIFIED")

    def test_exact_duplicate_is_idempotent(self):
        self.ledger.append(task_id="t", generation=1, slot="a", fence=1, payload={"x": 1})
        replay = self.ledger.append(task_id="t", generation=1, slot="a", fence=1, payload={"x": 1})
        self.assertTrue(replay["idempotent_replay"])

    def test_divergent_duplicate_rejected(self):
        self.ledger.append(task_id="t", generation=1, slot="a", fence=1, payload={"x": 1})
        with self.assertRaises(LedgerConflict):
            self.ledger.append(task_id="t", generation=1, slot="a", fence=1, payload={"x": 2})

    def test_stale_fence_and_bad_cas_rejected(self):
        first = self.ledger.append(task_id="t", generation=1, slot="a", fence=2, payload={"x": 1})
        with self.assertRaises(FenceRejected):
            self.ledger.append(task_id="t", generation=1, slot="b", fence=1, payload={"x": 2})
        with self.assertRaises(FenceRejected):
            self.ledger.append(task_id="t", generation=1, slot="b", fence=2, payload={"x": 2}, expected_head_hash="wrong")
        self.assertEqual(self.ledger.head("t")["receipt_hash"], first["receipt_hash"])


class HardContextCapsuleTests(unittest.TestCase):
    def source(self):
        return {
            "objective": "finish",
            "requirements": ["proof"],
            "constraints": ["safe"],
            "source_epochs": {"main": "abc"},
            "routes": ["drive"],
            "open_gates": [],
            "recent_failures": ["f" * 1500],
            "next_actions": ["n" * 1500],
            "notes": ["x" * 1500],
            "huge_archive": "z" * 10000,
        }

    def test_optional_sections_are_omitted_to_meet_budget(self):
        capsule = build_hard_context_capsule(self.source(), max_bytes=1000)
        self.assertLessEqual(capsule["bytes"], 1000)
        self.assertIn("huge_archive", capsule["omitted"])
        self.assertEqual(capsule["objective"], "finish")

    def test_required_context_cannot_be_silently_dropped(self):
        source = self.source()
        source["objective"] = "o" * 5000
        with self.assertRaises(HardContextCapsuleError):
            build_hard_context_capsule(source, max_bytes=500)


class StreamGuardTests(unittest.TestCase):
    def test_safe_stream_is_admitted(self):
        verdict = assess_stream({"payload_tokens": 1500, "concurrency": 3, "owner_visible_progress_events": 1})
        self.assertEqual(verdict["decision"], "ADMIT")

    def test_raw_or_attention_heavy_stream_is_quarantined(self):
        verdict = assess_stream({
            "payload_tokens": 5000,
            "raw_payload_serialized": True,
            "retry_count": 3,
            "owner_visible_progress_events": 9,
        })
        self.assertEqual(verdict["decision"], "QUARANTINE")
        self.assertIn("PAYLOAD_OVERFLOW", verdict["issues"])
        self.assertIn("RAW_PAYLOAD_SERIALIZED", verdict["issues"])
        self.assertIn("OWNER_ATTENTION_OVERFLOW", verdict["issues"])


if __name__ == "__main__":
    unittest.main()
