import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from evidenceops.build_system.chat_failure_resilience import (
    append_ledger,
    build_checkpoint,
    classify_failure,
    evaluate_failure,
)
from evidenceops.build_system.objective_completion_guard import REQUIRED_OPERATIONAL_LAYERS
from evidenceops.build_system.runtime_controls import (
    ACKNOWLEDGED,
    ORPHANED_UNACKNOWLEDGED,
    CancellationToken,
    CooperativeCancellation,
    DeliveryJournal,
    DistinctRouteCircuit,
    HeartbeatScheduler,
    HandoffStore,
    IntegrityError,
    NoSafeRoute,
    PolicyDenied,
    Route,
    RuntimePolicy,
)


def open_mission_packet():
    return {
        "mission": {
            "objective": "Complete the active workstream despite chat failures.",
            "terminalCriteria": [
                {"id": "WORK", "critical": True, "state": "OPEN"},
            ],
            "terminalFruit": ["completion receipt"],
        },
        "systemBuild": {"operationalLayers": {
            name: {"applicable": True, "state": "PROVEN"} for name in REQUIRED_OPERATIONAL_LAYERS
        }},
        "cycle": {
            "durationHours": 24,
            "elapsedHours": 1,
            "artifactComplete": False,
            "completionRequested": False,
            "assistantStopping": False,
            "reportingOpenWork": False,
            "movingToUnrelatedWork": False,
        },
        "execution": {
            "authorizedRouteAvailable": True,
            "nextAutomatedAction": "resume from checkpoint",
            "routeExhaustionProven": False,
            "manualUserTasksAllowed": False,
            "manualUserTasks": [],
        },
        "proof": {
            "observedTerminalFruit": [],
            "independentLiveReadback": True,
        },
    }


class ChatFailureResilienceTests(unittest.TestCase):
    def test_connection_interrupted_is_detected_without_root_cause_overclaim(self):
        candidates = classify_failure({
            "message": "Connection interrupted. Waiting for the complete answer",
            "network_online": True,
        })
        classes = {item.failure_class for item in candidates}
        self.assertIn("TRANSPORT_INTERRUPTION", classes)
        self.assertIn("STALL_TIMEOUT", classes)
        self.assertTrue(all(item.score < 1.0 for item in candidates))

    def test_screenshot_style_failure_forces_recovery_when_mission_open(self):
        receipt = evaluate_failure({
            "message": "Connection interrupted. Waiting for the complete answer",
            "active_directive": "Continue until all work is done",
            "next_pending_action": "finish release gate",
        }, mission_packet=open_mission_packet())
        self.assertTrue(receipt.must_continue)
        self.assertFalse(receipt.mission_complete)
        self.assertFalse(receipt.completion_claim_permitted)
        self.assertEqual("AUTOMATED_RECOVERY", receipt.recovery_mode)
        self.assertEqual("PERSIST_MISSION_CHECKPOINT", receipt.recovery_steps[0].action)
        self.assertFalse(receipt.provider_effects_claimed)

    def test_network_offline_strongly_supports_transport_failure(self):
        candidates = classify_failure({"message": "request failed", "network_online": False})
        primary = candidates[0]
        self.assertEqual("TRANSPORT_INTERRUPTION", primary.failure_class)
        self.assertGreaterEqual(primary.score, 0.9)

    def test_429_is_rate_limit_and_uses_bounded_retry_route(self):
        receipt = evaluate_failure({"http_status": 429, "message": "Too many requests"})
        self.assertEqual("RATE_OR_CAPACITY_LIMIT", receipt.failure_class)
        self.assertIn("RETRY_SAME_ATOMIC_ACTION", [step.action for step in receipt.recovery_steps])
        self.assertTrue(receipt.must_continue)

    def test_context_pressure_compacts_then_handoffs(self):
        receipt = evaluate_failure({
            "message": "conversation too long; context limit reached",
            "conversation_turns": 300,
            "active_directive": "complete current mission",
            "next_pending_action": "continue evidence review",
        })
        actions = [step.action for step in receipt.recovery_steps]
        self.assertEqual("CONTEXT_PRESSURE", receipt.failure_class)
        self.assertIn("COMPACT_CONTINUITY_STATE", actions)
        self.assertIn("START_FRESH_EXECUTION_CONTEXT", actions)

    def test_tool_timeout_requires_readback_before_replay(self):
        receipt = evaluate_failure({
            "message": "tool call timeout",
            "tool_inflight": True,
            "tool_call_id": "tool-123",
            "next_pending_action": "write provider record",
        })
        actions = [step.action for step in receipt.recovery_steps]
        self.assertEqual("TOOL_OR_CONNECTOR_FAILURE", receipt.failure_class)
        self.assertIn("READBACK_TOOL_OUTCOME_BEFORE_RETRY", actions)
        self.assertLess(actions.index("READBACK_TOOL_OUTCOME_BEFORE_RETRY"), actions.index("DISCOVER_EQUIVALENT_AUTHORIZED_ROUTE"))

    def test_auth_failure_preserves_action_without_blind_replay(self):
        receipt = evaluate_failure({
            "http_status": 401,
            "message": "session expired",
            "next_pending_action": "external mutation",
        })
        actions = [step.action for step in receipt.recovery_steps]
        self.assertEqual("AUTH_OR_SESSION_FAILURE", receipt.failure_class)
        self.assertIn("PRESERVE_PENDING_ACTION_WITHOUT_REPLAY", actions)
        self.assertNotIn("RETRY_SAME_ATOMIC_ACTION", actions)

    def test_user_cancel_is_respected(self):
        receipt = evaluate_failure({"message": "user cancelled"})
        self.assertEqual("USER_INTERRUPTION", receipt.failure_class)
        self.assertFalse(receipt.must_continue)
        self.assertEqual("PRESERVE_AND_AWAIT_USER_RESUME", receipt.recovery_mode)
        self.assertEqual("WAIT_FOR_USER_RESUME", receipt.next_automated_action)

    def test_large_non_atomic_work_is_decomposed(self):
        receipt = evaluate_failure({
            "message": "Connection interrupted",
            "atomic_action": False,
            "payload_large": True,
        })
        self.assertIn(
            "DECOMPOSE_INTO_CHECKPOINTED_ATOMIC_STEPS",
            [step.action for step in receipt.recovery_steps],
        )

    def test_checkpoint_resume_and_idempotency_keys_are_stable_across_time(self):
        event = {
            "active_directive": "finish mission",
            "objective": "prove completion",
            "last_completed_action": "A",
            "next_pending_action": "B",
            "tool_call_id": "T",
            "conversation_id": "C",
        }
        first = build_checkpoint(event)
        second = build_checkpoint(event)
        self.assertEqual(first["resume_token"], second["resume_token"])
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])

    def test_unknown_failure_enters_route_discovery_not_false_completion(self):
        receipt = evaluate_failure({"message": "opaque failure xyz"})
        self.assertEqual("UNKNOWN_CHAT_FAILURE", receipt.failure_class)
        self.assertTrue(receipt.must_continue)
        self.assertFalse(receipt.completion_claim_permitted)
        self.assertIn("DISCOVER_LOWEST_RISK_RECOVERY_ROUTE", [step.action for step in receipt.recovery_steps])

    def test_route_exhaustion_is_blocked_state_not_completion(self):
        receipt = evaluate_failure({
            "message": "connector unavailable",
            "route_exhaustion_proven": True,
        })
        self.assertFalse(receipt.must_continue)
        self.assertFalse(receipt.mission_complete)
        self.assertFalse(receipt.completion_claim_permitted)
        self.assertEqual("PRESERVE_BLOCKED_STATE", receipt.recovery_mode)

    def test_ledger_is_persistent_atomic_and_idempotent_by_receipt(self):
        receipt = evaluate_failure({
            "event_id": "evt-ledger",
            "message": "Connection interrupted",
            "active_directive": "finish",
            "next_pending_action": "resume",
        })
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.json"
            first = append_ledger(path, receipt)
            second = append_ledger(path, receipt)
            self.assertEqual(1, first["event_count"])
            self.assertEqual(1, second["event_count"])
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(receipt.receipt_sha256, on_disk["latest_receipt_sha256"])
            self.assertEqual(receipt.checkpoint["resume_token"], on_disk["latest_checkpoint"]["resume_token"])

    def test_background_heartbeat_runs_without_caller_polling_and_stops(self):
        heartbeats = []
        observed = threading.Event()

        def capture(heartbeat):
            heartbeats.append(heartbeat)
            if len(heartbeats) >= 2:
                observed.set()

        scheduler = HeartbeatScheduler(0.01, capture)
        scheduler.start()
        self.assertTrue(observed.wait(1.0), heartbeats)
        self.assertTrue(scheduler.stop())
        self.assertFalse(scheduler.is_running)
        self.assertEqual([1, 2], [item.sequence for item in heartbeats[:2]])
        self.assertIsNone(scheduler.callback_error)

    def test_shared_cancellation_persists_and_preempts_at_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "control.sqlite3"
            first = CancellationToken(database, "mission-1")
            second = CancellationToken(database, "mission-1")
            first.checkpoint()
            first.cancel("owner stop")
            with self.assertRaisesRegex(CooperativeCancellation, "owner stop"):
                second.checkpoint()

    def test_open_circuit_selects_a_deterministic_distinct_route(self):
        with tempfile.TemporaryDirectory() as temp:
            circuit = DistinctRouteCircuit(
                Path(temp) / "routes.sqlite3",
                [Route("primary", 100), Route("fallback-b", 50), Route("fallback-a", 50)],
            )
            circuit.open("primary", "sha256:failure")
            self.assertEqual("fallback-a", circuit.select_distinct("primary").route_id)

    def test_retry_fails_closed_when_no_distinct_authorized_route_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            circuit = DistinctRouteCircuit(
                Path(temp) / "routes.sqlite3",
                [Route("primary", 100), Route("provider", 90, provider_effect=True)],
            )
            circuit.open("primary", "sha256:failure")
            with self.assertRaises(NoSafeRoute):
                circuit.select_distinct("primary", providers_enabled=False)

    def test_handoff_is_hash_verified_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "handoff.json"
            store = HandoffStore(path)
            payload = {"directive": "continue", "next_action": "canary"}
            store.write("tx-handoff", payload)
            self.assertEqual(payload, store.read("tx-handoff"))
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["payload"]["next_action"] = "mutated"
            path.write_text(json.dumps(envelope), encoding="utf-8")
            with self.assertRaises(IntegrityError):
                store.read("tx-handoff")

    def test_terminal_delivery_marks_orphan_or_atomic_ack_and_chain_verifies(self):
        with tempfile.TemporaryDirectory() as temp:
            journal = DeliveryJournal(Path(temp) / "delivery.sqlite3")
            orphan = journal.deliver("tx-orphan", "artifact-1", "sha256:a", acknowledgement=None)
            acknowledged = journal.deliver(
                "tx-ack", "artifact-2", "sha256:b", acknowledgement="owner-visible-response"
            )
            self.assertEqual(ORPHANED_UNACKNOWLEDGED, orphan["state"])
            self.assertEqual(ACKNOWLEDGED, acknowledged["state"])
            self.assertTrue(journal.verify_event_chain())

    def test_provider_effect_is_blocked_by_default(self):
        with self.assertRaisesRegex(PolicyDenied, "provider actions are disabled"):
            RuntimePolicy().admit("PROVIDER_WRITE")

    def test_new_system_identity_is_rejected(self):
        with self.assertRaisesRegex(PolicyDenied, "new system identity"):
            RuntimePolicy().admit("LOCAL_TEST", target_identity="CFRE-OMEGA-REPLACEMENT")


if __name__ == "__main__":
    unittest.main()
