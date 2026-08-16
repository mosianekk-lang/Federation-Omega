import json
import unittest

from bubbles.command_bus import build_receipt


class BubblesForestBackgroundEventTests(unittest.TestCase):
    def command(self, **overrides):
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
        event.update(overrides)
        return {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": "bubbles_command_bus",
            "action": "forest_first_omega_event",
            "effect": "READ",
            "target_alias": "FOREST_FIRST_OMEGA_BACKGROUND_RUNTIME",
            "payload": {"event": event},
        }

    def run_command(self, command):
        return build_receipt(
            json.dumps(command),
            actor="mosianekk-lang",
            event_name="workflow_dispatch",
            source_ref="SANITIZED_EVENT_TEST",
        )

    def test_low_materiality_event_is_c0_and_quiet(self):
        receipt = self.run_command(self.command())
        self.assertEqual("SUCCESS", receipt["state"])
        background = receipt["execution"]["background_receipt"]
        self.assertEqual("ALLOW", background["cost"]["action"])
        self.assertEqual(0.0, background["cost"]["permitted_incremental_cost"])
        self.assertFalse(background["private_reasoning_wake_required"])
        self.assertFalse(background["owner_wake_required"])
        self.assertFalse(background["external_effect"])

    def test_material_legal_deadline_wakes_private_reasoning_and_owner(self):
        receipt = self.run_command(self.command(
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

    def test_private_content_is_rejected_before_public_receipt(self):
        receipt = self.run_command(self.command(private_content_included=True))
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("Private message/document content", receipt["reason"])

    def test_freeform_private_field_is_rejected(self):
        command = self.command()
        command["payload"]["event"]["subject"] = "must never enter public runner receipt"
        receipt = self.run_command(command)
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("unsupported fields", receipt["reason"])

    def test_invalid_fingerprint_is_rejected(self):
        receipt = self.run_command(self.command(fingerprint_sha256="not-a-digest"))
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("fingerprint_sha256", receipt["reason"])


if __name__ == "__main__":
    unittest.main()
