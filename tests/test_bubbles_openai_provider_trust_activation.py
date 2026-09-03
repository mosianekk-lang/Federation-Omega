from __future__ import annotations

import unittest

from bubbles.capability_activation import ActivationState, build_activation_snapshot


SOURCE = "cf789af9da3155b8f427133e2e11693e93e48ed8"


class OpenAIProviderTrustActivationTests(unittest.TestCase):
    def lane(self, snapshot: dict, lane_id: str) -> dict:
        return next(lane for lane in snapshot["lanes"] if lane["lane_id"] == lane_id)

    def test_authenticated_billing_block_is_provider_gated_not_credential_gated(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            openai_provider_trust_receipt={
                "schema": "FEDOMEGA-PROVIDER-TRUST-RESOLUTION-1",
                "credential_reference_found": True,
                "runtime_bound": True,
                "provider_authenticated": True,
                "provider_live_verified": False,
                "state": "BLOCKED_PROVIDER_BILLING",
                "provider_error_code": "credit_balance_exhausted",
                "next_action": "RESTORE_PROVIDER_BILLING",
                "secret_value_recorded": False,
            },
        )
        lane = self.lane(snapshot, "OPENAI_PROVIDER_LIVE")
        self.assertEqual(ActivationState.PROVIDER_GATED.value, lane["state"])
        self.assertEqual(
            "RESTORE_PROVIDER_BILLING_THEN_REUSE_BOUNDED_PROVIDER_LIVE_CANARY",
            lane["next_gate"],
        )
        self.assertTrue(snapshot["openai_provider_trust"]["provider_authenticated"])
        self.assertEqual("credit_balance_exhausted", snapshot["openai_provider_trust"]["provider_error_code"])

    def test_provider_live_verified_promotes_hosted_verified(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            openai_provider_trust_receipt={
                "credential_reference_found": True,
                "runtime_bound": True,
                "provider_authenticated": True,
                "provider_live_verified": True,
                "state": "PROVIDER_LIVE_VERIFIED",
            },
        )
        lane = self.lane(snapshot, "OPENAI_PROVIDER_LIVE")
        self.assertEqual(ActivationState.HOSTED_VERIFIED.value, lane["state"])
        self.assertIsNone(lane["next_gate"])

    def test_missing_runtime_binding_remains_credential_gated(self) -> None:
        snapshot = build_activation_snapshot(
            source_sha=SOURCE,
            event_name="push",
            openai_provider_trust_receipt={},
        )
        lane = self.lane(snapshot, "OPENAI_PROVIDER_LIVE")
        self.assertEqual(ActivationState.CREDENTIAL_GATED.value, lane["state"])


if __name__ == "__main__":
    unittest.main()
