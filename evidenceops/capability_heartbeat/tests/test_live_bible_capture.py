from __future__ import annotations

import hashlib
import unittest

from evidenceops.capability_heartbeat.engine import HeartbeatError
from evidenceops.capability_heartbeat.live_bible_capture import LiveBibleCaptureFabric


def fp(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class LiveBibleCaptureTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "schema": "EVIDENCEOPS-LIVE-BIBLE-CAPTURE-CONTRACT-2",
            "capture_version": 2,
            "node_id": "NODE-TEST-LIVE-BIBLE",
            "privacy_tier": "P2",
            "max_seen_fingerprints": 128,
            "sources": [
                {
                    "source_id": "SRC-CHAT",
                    "kind": "CHATGPT_ACTIVE_TURN",
                    "allowed_modes": ["ACTIVE_TURN", "RECOVERY_REPLAY"],
                    "supports_between_turn": False,
                    "provider_receipt_required": False,
                    "privacy_ceiling": "P2",
                    "materiality_threshold": 0.3,
                    "master_promotion_allowed": False,
                },
                {
                    "source_id": "SRC-GITHUB",
                    "kind": "GITHUB_REPOSITORY",
                    "allowed_modes": ["SCHEDULED_RECONCILIATION", "PROVIDER_EVENT"],
                    "supports_between_turn": True,
                    "provider_receipt_required": True,
                    "privacy_ceiling": "P1",
                    "materiality_threshold": 0.5,
                    "master_promotion_allowed": True,
                },
            ],
        }
        self.fabric = LiveBibleCaptureFabric(self.contract)
        self.now = "2026-08-04T17:00:00+00:00"

    def event(self, **overrides):
        values = dict(
            source_id="SRC-CHAT",
            source_event_id="EV-001",
            capture_mode="ACTIVE_TURN",
            occurred_at="2026-08-04T16:59:00+00:00",
            observed_at=self.now,
            event_type="USER_DIRECTIVE",
            summary="A material owner directive was captured.",
            content_fingerprint=fp("event-1"),
            source_cursor="turn-1",
            privacy_tier="P2",
            materiality=0.9,
            provider_receipt_ref=None,
            workstream_id="WS-A-LB",
        )
        values.update(overrides)
        return self.fabric.make_event(**values)

    def test_active_turn_is_captured(self):
        result = self.fabric.reconcile([self.event()], previous_state=None, observed_at=self.now)
        self.assertEqual(result["receipt"]["capture_state"], "CAPTURED_MATERIAL_DELTA")
        self.assertEqual(len(result["accepted_deltas"]), 1)
        self.assertFalse(result["accepted_deltas"][0]["master_promotion_eligible"])

    def test_between_turn_chat_source_is_held(self):
        event = self.event(capture_mode="RECOVERY_REPLAY", source_event_id="EV-002", content_fingerprint=fp("event-2"))
        result = self.fabric.reconcile([event], previous_state=None, observed_at=self.now)
        self.assertIn("BETWEEN_TURN_SOURCE_NOT_AVAILABLE", result["held_events"][0]["reasons"])

    def test_provider_event_requires_receipt(self):
        event = self.fabric.make_event(
            source_id="SRC-GITHUB",
            source_event_id="GH-001",
            capture_mode="SCHEDULED_RECONCILIATION",
            occurred_at=self.now,
            observed_at=self.now,
            event_type="GITHUB_COMMIT",
            summary="Commit observed.",
            content_fingerprint=fp("gh-1"),
            source_cursor="sha-1",
            privacy_tier="P1",
            materiality=0.9,
        )
        result = self.fabric.reconcile([event], previous_state=None, observed_at=self.now)
        self.assertIn("PROVIDER_RECEIPT_REQUIRED", result["held_events"][0]["reasons"])

    def test_provider_event_with_receipt_is_captured_and_promotable(self):
        event = self.fabric.make_event(
            source_id="SRC-GITHUB",
            source_event_id="GH-002",
            capture_mode="SCHEDULED_RECONCILIATION",
            occurred_at=self.now,
            observed_at=self.now,
            event_type="GITHUB_COMMIT",
            summary="Verified provider commit observed.",
            content_fingerprint=fp("gh-2"),
            source_cursor="sha-2",
            privacy_tier="P1",
            materiality=0.9,
            provider_receipt_ref="github:test/repo@sha-2",
        )
        result = self.fabric.reconcile([event], previous_state=None, observed_at=self.now)
        self.assertTrue(result["accepted_deltas"][0]["master_promotion_eligible"])

    def test_duplicate_is_idempotent(self):
        first = self.fabric.reconcile([self.event()], previous_state=None, observed_at=self.now)
        second = self.fabric.reconcile([self.event()], previous_state=first["state"], observed_at=self.now)
        self.assertEqual(second["receipt"]["capture_state"], "NO_MATERIAL_CHANGE")
        self.assertEqual(len(second["duplicate_event_refs"]), 1)

    def test_cursor_conflict_is_quarantined(self):
        first = self.fabric.reconcile([self.event()], previous_state=None, observed_at=self.now)
        conflicting = self.event(source_event_id="EV-003", content_fingerprint=fp("event-3"), source_cursor="turn-1")
        second = self.fabric.reconcile([conflicting], previous_state=first["state"], observed_at=self.now)
        self.assertEqual(second["receipt"]["capture_state"], "CONFLICT_HELD")
        self.assertIn("CURSOR_CONTENT_CONFLICT", second["conflicts"][0]["reasons"])

    def test_low_materiality_is_held(self):
        result = self.fabric.reconcile([self.event(materiality=0.1)], previous_state=None, observed_at=self.now)
        self.assertIn("BELOW_MATERIALITY_THRESHOLD", result["held_events"][0]["reasons"])

    def test_raw_content_and_credentials_are_rejected(self):
        event = self.event()
        event["credentials_included"] = True
        event.pop("event_sha256")
        with self.assertRaises(HeartbeatError):
            self.fabric.verify_event(event)

    def test_tampered_state_is_rejected(self):
        state = self.fabric.empty_state(self.contract["node_id"])
        state["accepted_event_count"] = 10
        with self.assertRaises(HeartbeatError):
            self.fabric.verify_state(state, self.contract["node_id"])

    def test_tampered_receipt_is_rejected(self):
        result = self.fabric.reconcile([self.event()], previous_state=None, observed_at=self.now)
        receipt = dict(result["receipt"])
        receipt["external_effects"] = 1
        with self.assertRaises(HeartbeatError):
            self.fabric.verify_receipt(receipt)

    def test_future_event_is_held(self):
        future = self.event(observed_at="2026-08-04T18:00:00+00:00")
        result = self.fabric.reconcile([future], previous_state=None, observed_at=self.now)
        self.assertIn("EVENT_OBSERVED_IN_FUTURE", result["held_events"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
