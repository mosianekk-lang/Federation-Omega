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

    def background_command(self, **event_overrides):
        event = {
            "schema": "BUBBLES-FOREST-BACKGROUND-EVENT-V1",
            "event_id": "evt-001",
            "source_class": "FEDERATION_STATE",
            "event_class": "STATE_CHANGE",
            "fingerprint_sha256": "a" * 64,
            "matter_class": "SYSTEM",
            "materiality": 0.2,
            "consequence": 0.3,
            "uncertainty": 0.2,
            "dependency_density": 0.2,
            "adversarial_complexity": 0.1,
            "deadline_risk": False,
            "evidence_risk": False,
            "owner_only": False,
            "provider_readback_missing": False,
            "route_failure": False,
            "objective_exhausted": False,
            "material_strategy_change": False,
            "private_content_included": False,
        }
        event.update(event_overrides)
        return self.command(
            action="forest_first_omega_event",
            effect="READ",
            target_alias="FOREST_FIRST_OMEGA_BACKGROUND_RUNTIME",
            payload={"event": event},
        )

    def test_internal_canary_succeeds_without_external_provider_effect(self):
        receipt = self.run_command(self.command())
        self.assertEqual(receipt["state"], "SUCCESS")
        self.assertEqual(receipt["execution"]["kind"], "LOCAL_COMMAND_BUS_CANARY")
        self.assertIn("does not prove Google Cloud", receipt["truth_boundary"])

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

    def test_background_low_materiality_event_stays_quiet_and_c0(self):
        receipt = self.run_command(self.background_command())
        self.assertEqual("SUCCESS", receipt["state"])
        execution = receipt["execution"]
        self.assertEqual("LOCAL_FOREST_FIRST_OMEGA_BACKGROUND_EVENT", execution["kind"])
        background = execution["background_receipt"]
        self.assertEqual("ALLOW", background["cost"]["action"])
        self.assertEqual(0.0, background["cost"]["permitted_incremental_cost"])
        self.assertFalse(background["owner_wake_required"])
        self.assertFalse(background["private_reasoning_wake_required"])
        self.assertFalse(background["external_effect"])

    def test_background_material_legal_deadline_wakes_private_reasoning_and_owner(self):
        receipt = self.run_command(self.background_command(
            event_id="evt-deadline",
            source_class="GMAIL_METADATA",
            event_class="DEADLINE_CHANGE",
            matter_class="LEGAL",
            materiality=0.95,
            consequence=0.95,
            uncertainty=0.6,
            deadline_risk=True,
        ))
        background = receipt["execution"]["background_receipt"]
        self.assertTrue(background["private_reasoning_wake_required"])
        self.assertTrue(background["owner_wake_required"])
        self.assertGreaterEqual(background["forest"]["adaptive_horizon_depth"], 10)
        self.assertEqual("ALLOW", background["cost"]["action"])

    def test_background_rejects_private_content_from_public_event_envelope(self):
        receipt = self.run_command(self.background_command(private_content_included=True))
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("Private message/document content", receipt["reason"])

    def test_background_rejects_unapproved_freeform_fields(self):
        command = self.background_command()
        command["payload"]["event"]["subject"] = "private subject must not enter public receipt"
        receipt = self.run_command(command)
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("unsupported fields", receipt["reason"])

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
