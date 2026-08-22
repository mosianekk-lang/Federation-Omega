import json
import unittest

from bubbles.command_bus import build_receipt
from bubbles.control_plane import ActionRequest, BubblesControlPlane, EffectClass


class BubblesCommandBusTests(unittest.TestCase):
    def command(self, **overrides):
        base = {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": "bubbles_command_bus",
            "action": "canary",
            "effect": "READ",
            "target_alias": "GITHUB_ACTIONS_A0_A1",
            "payload": {"message": "CHATGPT_TO_ACTIONS_CANARY"},
        }
        base.update(overrides)
        return base

    def run_command(self, command, actor="mosianekk-lang"):
        return build_receipt(
            json.dumps(command),
            actor=actor,
            event_name="pull_request",
            source_ref="PR-CANARY",
        )

    def recovery_command(self, event, **payload_overrides):
        payload = {"event": event, **payload_overrides}
        return self.command(
            action="recover_chat_failure",
            effect="READ",
            target_alias="EVIDENCEOPS_CFRE_LOCAL",
            payload=payload,
        )

    def benchmark_command(self, action="jarvis_benchmark_validate", payload=None):
        return self.command(
            action=action,
            effect="READ",
            target_alias="JARVIS_BENCHMARK_PUBLIC_FIXTURE_V1",
            payload=payload or {},
        )

    def test_internal_canary_succeeds_without_external_provider_effect(self):
        receipt = self.run_command(self.command())
        self.assertEqual(receipt["state"], "SUCCESS")
        self.assertEqual(receipt["execution"]["kind"], "LOCAL_COMMAND_BUS_CANARY")
        self.assertIn("does not prove Google Cloud", receipt["truth_boundary"])

    def test_jarvis_benchmark_runs_as_read_only_central_task_module(self):
        receipt = self.run_command(self.benchmark_command())
        self.assertEqual("SUCCESS", receipt["state"])
        execution = receipt["execution"]
        self.assertEqual("LOCAL_JARVIS_BENCHMARK_CONTROL_PLANE", execution["kind"])
        self.assertTrue(execution["result"]["valid"])
        self.assertFalse(execution["providerEffects"])
        self.assertFalse(execution["networkUsed"])
        self.assertFalse(execution["runtimeLedgerPersisted"])
        self.assertIn("public fixture", receipt["truth_boundary"])

    def test_jarvis_benchmark_rejects_private_payload_and_write_route(self):
        private = self.run_command(self.benchmark_command(
            action="jarvis_benchmark_snapshot",
            payload={"state": {"private": "must-not-enter-public-command-bus"}},
        ))
        self.assertEqual("FAILURE", private["state"])
        self.assertIn("unknown fields", private["reason"])

        write_route = self.run_command(self.benchmark_command(
            action="jarvis_benchmark_cycle_commit",
        ))
        self.assertEqual("CONSTRAINT", write_route["state"])
        self.assertIn("not bound", write_route["reason"])

    def test_chat_failure_recovery_invokes_cfre_for_connection_interruption(self):
        receipt = self.run_command(self.recovery_command({
            "message": "Connection interrupted. Waiting for the complete answer",
            "active_directive": "continue until complete",
            "next_pending_action": "resume current operation",
        }))
        self.assertEqual("SUCCESS", receipt["state"])
        self.assertEqual("LOCAL_CHAT_FAILURE_RECOVERY", receipt["execution"]["kind"])
        recovery = receipt["execution"]["recovery"]
        self.assertEqual("TRANSPORT_INTERRUPTION", recovery["failure_class"])
        self.assertTrue(recovery["must_continue"])
        self.assertEqual("RETRY_SAME_ATOMIC_ACTION", recovery["next_automated_action"])
        self.assertFalse(receipt["execution"]["provider_effects"])

    def test_chat_failure_recovery_uses_readback_before_tool_timeout_replay(self):
        receipt = self.run_command(self.recovery_command({
            "message": "tool call timeout",
            "tool_inflight": True,
            "tool_call_id": "tool-write-1",
            "next_pending_action": "finish provider write",
        }))
        recovery = receipt["execution"]["recovery"]
        self.assertEqual("TOOL_OR_CONNECTOR_FAILURE", recovery["failure_class"])
        self.assertEqual("READBACK_TOOL_OUTCOME_BEFORE_RETRY", recovery["next_automated_action"])
        actions = [step["action"] for step in recovery["recovery_steps"]]
        self.assertLess(
            actions.index("READBACK_TOOL_OUTCOME_BEFORE_RETRY"),
            actions.index("DISCOVER_EQUIVALENT_AUTHORIZED_ROUTE"),
        )

    def test_chat_failure_recovery_respects_explicit_user_stop(self):
        receipt = self.run_command(self.recovery_command({"message": "user cancelled"}))
        recovery = receipt["execution"]["recovery"]
        self.assertEqual("USER_INTERRUPTION", recovery["failure_class"])
        self.assertFalse(recovery["must_continue"])
        self.assertEqual("WAIT_FOR_USER_RESUME", recovery["next_automated_action"])

    def test_recovery_requires_event_object(self):
        receipt = self.run_command(self.command(
            action="recover_chat_failure",
            effect="READ",
            target_alias="EVIDENCEOPS_CFRE_LOCAL",
            payload={"event": "not-an-object"},
        ))
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("payload.event", receipt["reason"])

    def test_unapproved_actor_is_blocked(self):
        receipt = self.run_command(self.command(), actor="untrusted-user")
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("not allowed", receipt["reason"])

    def test_provider_route_is_blocked_without_fresh_runtime_proofs(self):
        receipt = self.run_command(
            self.command(
                adapter_id="google_cloud",
                action="run_harmless_canary",
                effect="LOW_RISK_WRITE",
                target_alias="GOOGLE_CLOUD_EXECUTION_PLANE",
                payload={},
            )
        )
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("provider_identity_verified", receipt["missing_proofs"])
        self.assertIn("no provider action executed", receipt["truth_boundary"].lower())

    def test_secret_bearing_payload_fails_validation(self):
        receipt = self.run_command(
            self.command(payload={"api_key": "never-store-me"})
        )
        self.assertEqual(receipt["state"], "FAILURE")
        self.assertIn("Secret-bearing", receipt["reason"])

    def test_tampered_command_hash_is_rejected(self):
        control = BubblesControlPlane()
        request = ActionRequest(
            adapter_id="bubbles_command_bus",
            action="canary",
            effect=EffectClass.READ,
            target_alias="GITHUB_ACTIONS_A0_A1",
            payload={"message": "CHATGPT_TO_ACTIONS_CANARY"},
        )
        command = control.command_envelope(request)
        command["command_sha256"] = "0" * 64
        receipt = self.run_command(command)
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("does not match", receipt["reason"])

    def test_native_route_cannot_be_smuggled_through_command_bus(self):
        receipt = self.run_command(
            self.command(
                adapter_id="github",
                action="enqueue",
                effect="READ",
                target_alias="FEDERATION_OMEGA_CONTROL_PLANE",
                payload={},
            )
        )
        self.assertEqual(receipt["state"], "CONSTRAINT")
        self.assertIn("GITHUB_COMMAND_BUS", receipt["reason"])


if __name__ == "__main__":
    unittest.main()
