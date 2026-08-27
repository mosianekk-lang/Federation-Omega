import unittest

from ao_harmonic_v3.failure_win_manifest import compile_receiver_manifest


def registry(*names):
    return [
        {
            "receiver_id": name,
            "canonical_control": f"{name} control",
            "primary_id": f"id-{name}",
            "active": True,
        }
        for name in names
    ]


class FailureWinReceiverManifestTests(unittest.TestCase):
    def compile(self, rows, events=(), complete=True, aliases=()):
        return compile_receiver_manifest(
            rows,
            events,
            generated_from="fixture",
            generated_at="2026-08-27T04:00:00+02:00",
            source_complete=complete,
            receiver_alias_rows=aliases,
        )

    def test_clean_registry_is_structurally_complete_but_behavior_pending(self):
        result = self.compile(registry("A", "B"))
        self.assertTrue(result.complete)
        self.assertFalse(result.behavior_complete)
        self.assertEqual(2, result.receiver_count)
        self.assertEqual(
            {"REGISTERED_V2_BEHAVIOR_PENDING"},
            {item.receiver_state for item in result.receivers},
        )

    def test_blank_receiver_fails_manifest_complete(self):
        rows = registry("A") + [{"receiver_id": "", "primary_id": "id-x", "active": True}]
        result = self.compile(rows)
        self.assertFalse(result.complete)
        self.assertIn("BLANK_RECEIVER_ID", {item.code for item in result.anomalies})

    def test_duplicate_receiver_fails_manifest_complete(self):
        rows = registry("A") + registry("A")
        result = self.compile(rows)
        self.assertFalse(result.complete)
        self.assertIn("DUPLICATE_RECEIVER_ID", {item.code for item in result.anomalies})

    def test_unknown_event_receiver_fails_manifest_complete(self):
        events = [{"event_id": "E1", "receiver_id": "B", "kernel_version": "2.0.0"}]
        result = self.compile(registry("A"), events)
        self.assertFalse(result.complete)
        self.assertIn("UNKNOWN_EVENT_RECEIVER", {item.code for item in result.anomalies})

    def test_explicit_alias_normalizes_event_without_rewriting_source_label(self):
        events = [{
            "event_id": "E-ALIAS",
            "timestamp": "2026-08-27T00:00:00Z",
            "receiver_id": "A work-unit label",
            "kernel_version": "2.0.0",
            "kernel_invoked": True,
            "behavior_proven": False,
            "independent_readback": True,
            "current": True,
            "evidence_refs": ["R-A"],
        }]
        aliases = [{
            "alias": "A work-unit label",
            "canonical_receiver": "A",
            "current": True,
        }]
        result = self.compile(registry("A"), events, aliases=aliases)
        self.assertTrue(result.complete)
        self.assertEqual("V2_INVOKED_PROOF_OPEN", result.receivers[0].receiver_state)
        self.assertIn("RECEIVER_ALIAS_APPLIED", {item.code for item in result.anomalies})

    def test_alias_to_unknown_receiver_fails_closed(self):
        aliases = [{
            "alias": "legacy-a",
            "canonical_receiver": "MISSING",
            "current": True,
        }]
        result = self.compile(registry("A"), aliases=aliases)
        self.assertFalse(result.complete)
        self.assertIn("UNKNOWN_RECEIVER_ALIAS_TARGET", {item.code for item in result.anomalies})

    def test_alias_cannot_shadow_different_canonical_receiver(self):
        aliases = [{
            "alias": "A",
            "canonical_receiver": "B",
            "current": True,
        }]
        result = self.compile(registry("A", "B"), aliases=aliases)
        self.assertFalse(result.complete)
        self.assertIn("ALIAS_SHADOWS_CANONICAL_RECEIVER", {item.code for item in result.anomalies})

    def test_v1_behavior_proof_does_not_promote_v2(self):
        events = [{
            "event_id": "E1",
            "timestamp": "2026-08-23T00:00:00Z",
            "receiver_id": "A",
            "kernel_version": "1.0.0",
            "kernel_invoked": True,
            "behavior_proven": True,
            "independent_readback": True,
            "current": True,
            "evidence_refs": ["R1"],
        }]
        result = self.compile(registry("A"), events)
        receiver = result.receivers[0]
        self.assertEqual("V1_BEHAVIOR_PROVEN_V2_PENDING", receiver.receiver_state)
        self.assertFalse(receiver.kernel_invoked)
        self.assertFalse(receiver.behavior_proven)

    def test_v2_invocation_without_full_proof_stays_open(self):
        events = [{
            "event_id": "E2",
            "timestamp": "2026-08-27T00:00:00Z",
            "receiver_id": "A",
            "kernel_version": "2.0.0",
            "kernel_invoked": True,
            "behavior_proven": False,
            "independent_readback": True,
            "current": True,
            "evidence_refs": ["R2"],
        }]
        result = self.compile(registry("A"), events)
        self.assertEqual("V2_INVOKED_PROOF_OPEN", result.receivers[0].receiver_state)
        self.assertFalse(result.behavior_complete)

    def test_v2_behavior_requires_invocation_readback_current_and_evidence(self):
        events = [{
            "event_id": "E3",
            "timestamp": "2026-08-27T00:00:00Z",
            "receiver_id": "A",
            "kernel_version": "2.0.0",
            "kernel_invoked": True,
            "behavior_proven": True,
            "independent_readback": True,
            "current": True,
            "evidence_refs": ["R3"],
        }]
        result = self.compile(registry("A"), events)
        self.assertTrue(result.behavior_complete)
        self.assertEqual("V2_BEHAVIOR_PROVEN", result.receivers[0].receiver_state)

    def test_latest_event_controls_projection(self):
        events = [
            {"event_id": "E1", "timestamp": "2026-08-26T00:00:00Z", "receiver_id": "A", "kernel_version": "1.0.0", "behavior_proven": True},
            {"event_id": "E2", "timestamp": "2026-08-27T00:00:00Z", "receiver_id": "A", "kernel_version": "2.0.0", "kernel_invoked": True, "independent_readback": True, "current": True, "evidence_refs": ["R2"]},
        ]
        result = self.compile(registry("A"), events)
        self.assertEqual("E2", result.receivers[0].latest_event_id)
        self.assertEqual("V2_INVOKED_PROOF_OPEN", result.receivers[0].receiver_state)

    def test_hash_is_stable_across_input_order(self):
        rows1 = registry("A", "B")
        rows2 = list(reversed(rows1))
        first = self.compile(rows1)
        second = self.compile(rows2)
        self.assertEqual(first.snapshot_sha256, second.snapshot_sha256)

    def test_hash_changes_when_receiver_universe_changes(self):
        first = self.compile(registry("A"))
        second = self.compile(registry("A", "B"))
        self.assertNotEqual(first.snapshot_sha256, second.snapshot_sha256)


if __name__ == "__main__":
    unittest.main()
