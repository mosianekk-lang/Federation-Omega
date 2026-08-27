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


def complete_v2_behavior_event(**overrides):
    event = {
        "event_id": "E-BEHAVIOR",
        "timestamp": "2026-08-27T00:00:00Z",
        "receiver_id": "A",
        "kernel_version": "2.0.0",
        "kernel_invoked": True,
        "behavior_proven": True,
        "independent_readback": True,
        "current": True,
        "evidence_refs": ["R-BEHAVIOR"],
        "failure_fact_preserved": True,
        "causal_falsification": True,
        "different_route": True,
        "vector_gate": True,
        "failure_first": True,
        "healthy_path": True,
        "rollback": True,
        "forward_canary": True,
        "semantic_readback": True,
        "positive_value": True,
        "no_regression": True,
        "no_burden_increase": True,
        "repeated_successes": 3,
        "soak_seconds": 300,
    }
    event.update(overrides)
    return event


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

    def test_raw_v2_behavior_claim_without_proof_graph_is_rejected(self):
        event = {
            "event_id": "E-INCOMPLETE",
            "timestamp": "2026-08-27T00:00:00Z",
            "receiver_id": "A",
            "kernel_version": "2.0.0",
            "kernel_invoked": True,
            "behavior_proven": True,
            "independent_readback": True,
            "current": True,
            "evidence_refs": ["R-INCOMPLETE"],
        }
        result = self.compile(registry("A"), [event])
        receiver = result.receivers[0]
        self.assertTrue(result.complete)
        self.assertFalse(result.behavior_complete)
        self.assertFalse(receiver.behavior_proven)
        self.assertEqual("V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE", receiver.receiver_state)
        self.assertIn("BEHAVIOR_CLAIM_PROOF_INCOMPLETE", {item.code for item in result.anomalies})

    def test_v2_behavior_requires_complete_proof_graph_and_repeat_soak(self):
        result = self.compile(registry("A"), [complete_v2_behavior_event()])
        receiver = result.receivers[0]
        self.assertTrue(result.behavior_complete)
        self.assertTrue(receiver.behavior_proven)
        self.assertEqual("V2_BEHAVIOR_PROVEN", receiver.receiver_state)
        self.assertEqual(1, result.v2_behavior_proven_count)

    def test_two_successes_cannot_promote_behavior(self):
        result = self.compile(
            registry("A"),
            [complete_v2_behavior_event(event_id="E-REPEAT", repeated_successes=2)],
        )
        self.assertFalse(result.receivers[0].behavior_proven)
        self.assertEqual("V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE", result.receivers[0].receiver_state)
        detail = " ".join(item.detail for item in result.anomalies)
        self.assertIn("REPEATED_SUCCESSES<3", detail)

    def test_299_second_soak_cannot_promote_behavior(self):
        result = self.compile(
            registry("A"),
            [complete_v2_behavior_event(event_id="E-SOAK", soak_seconds=299)],
        )
        self.assertFalse(result.receivers[0].behavior_proven)
        self.assertEqual("V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE", result.receivers[0].receiver_state)
        detail = " ".join(item.detail for item in result.anomalies)
        self.assertIn("SOAK_SECONDS<300", detail)

    def test_sovara_style_provider_not_attempted_claim_fails_closed(self):
        event = complete_v2_behavior_event(
            event_id="FWV2-CURRENT-CHAT-SOVARA-REPAIR-20260827-001",
            receiver_id="Current Chat / SOVARA",
            vector_gate=False,
            failure_first=False,
            healthy_path=False,
            rollback=False,
            forward_canary=False,
            semantic_readback=False,
            positive_value=False,
            no_regression=False,
            no_burden_increase=False,
            repeated_successes=0,
            soak_seconds=0,
        )
        aliases = [{
            "alias": "Current Chat / SOVARA",
            "canonical_receiver": "SOVARA Ω",
            "current": True,
        }]
        result = self.compile(registry("SOVARA Ω"), [event], aliases=aliases)
        receiver = result.receivers[0]
        self.assertFalse(receiver.behavior_proven)
        self.assertEqual("V2_BEHAVIOR_CLAIM_PROOF_INCOMPLETE", receiver.receiver_state)
        codes = {item.code for item in result.anomalies}
        self.assertIn("RECEIVER_ALIAS_APPLIED", codes)
        self.assertIn("BEHAVIOR_CLAIM_PROOF_INCOMPLETE", codes)

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
