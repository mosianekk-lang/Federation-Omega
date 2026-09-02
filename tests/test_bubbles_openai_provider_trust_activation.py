from __future__ import annotations

import unittest

from bubbles.capability_activation import ActivationState, build_activation_snapshot


SOURCE = "5668d842ff52a0b84a9daf400e13506509927775"


def billing_blocked() -> dict:
    return {
        "provider": "openai",
        "credential_reference_found": True,
        "runtime_bound": True,
        "provider_authenticated": True,
        "provider_live_verified": False,
        "provider_error_code": "credit_balance_exhausted",
        "state": "BLOCKED_PROVIDER_BILLING",
        "next_action": "RESTORE_PROVIDER_BILLING",
        "secret_value_recorded": False,
        "receipt_sha256": "4" * 64,
    }


class BubblesOpenAIProviderTrustActivationTests(unittest.TestCase):
    def lane(self, snapshot: dict) -> dict:
        return next(lane for lane in snapshot["lanes"] if lane["lane_id"] == "OPENAI_PROVIDER_LIVE")

    def build(self, trust: dict | None = None) -> dict:
        return build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            provider_surface_receipt={},
            provider_authority_receipt={},
            openai_provider_trust_receipt=trust,
            schedule_configured=True,
        )

    def test_billing_block_is_provider_gated_not_credential_gated(self) -> None:
        lane = self.lane(self.build(billing_blocked()))
        self.assertEqual(ActivationState.PROVIDER_GATED.value, lane["state"])
        self.assertEqual("RESTORE_PROVIDER_BILLING", lane["next_gate"])

    def test_provider_live_receipt_promotes_only_openai_lane(self) -> None:
        trust = billing_blocked()
        trust.update(
            provider_live_verified=True,
            provider_error_code=None,
            state="PROVIDER_LIVE_VERIFIED",
            next_action=None,
        )
        snapshot = self.build(trust)
        lane = self.lane(snapshot)
        self.assertEqual(ActivationState.HOSTED_VERIFIED.value, lane["state"])
        self.assertIsNone(lane["next_gate"])
        self.assertFalse(snapshot["all_green"])

    def test_absent_receipt_remains_fail_closed(self) -> None:
        lane = self.lane(self.build())
        self.assertEqual(ActivationState.CREDENTIAL_GATED.value, lane["state"])

    def test_known_reference_without_binding_remains_credential_gated(self) -> None:
        lane = self.lane(self.build({
            "provider": "openai",
            "credential_reference_found": True,
            "runtime_bound": False,
            "provider_authenticated": False,
            "provider_live_verified": False,
            "secret_value_recorded": False,
        }))
        self.assertEqual(ActivationState.CREDENTIAL_GATED.value, lane["state"])


if __name__ == "__main__":
    unittest.main()
