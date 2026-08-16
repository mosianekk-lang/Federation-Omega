from __future__ import annotations

import unittest

from ao_harmonic_v3.provider_canary import ProviderObservation, ProviderObservationCanary


class ProviderObservationCanaryTests(unittest.TestCase):
    def observation(self, **overrides):
        values = {
            "provider": "Gmail",
            "capability": "READ_EMAIL_THREAD",
            "object_fingerprint": "a" * 64,
            "expected_status": "SENT",
            "observed_status": "SENT",
            "observed_at": "2026-08-16T17:40:00Z",
            "transport_ok": True,
            "semantic_match": True,
            "result_count": 1,
            "related_count": 0,
            "authority_ceiling": "A1_READ",
            "external_effect": False,
        }
        values.update(overrides)
        return ProviderObservation(**values)

    def test_successful_provider_readback_advances_only_bounded_canary(self):
        receipt = ProviderObservationCanary().run(self.observation())
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["maturity"], "CANARY_VALIDATED")
        self.assertFalse(receipt["external_effect"])
        self.assertIn("dependent_internal", receipt["ready_node_ids"])
        self.assertIn("unrelated_internal", receipt["ready_node_ids"])
        self.assertEqual(receipt["jarvis_defects"], [])
        self.assertFalse(receipt["truth_boundary"]["python_package_provider_deployed"])
        self.assertFalse(receipt["truth_boundary"]["workflow_verified"])
        self.assertFalse(receipt["truth_boundary"]["operationally_verified"])

    def test_semantic_status_mismatch_holds_promotion_and_blocks_dependent_lane(self):
        receipt = ProviderObservationCanary().run(
            self.observation(observed_status="DRAFT")
        )
        self.assertEqual(receipt["status"], "HOLD")
        self.assertEqual(receipt["maturity"], "SHADOW_VALIDATED")
        self.assertNotIn("dependent_internal", receipt["ready_node_ids"])
        self.assertIn("unrelated_internal", receipt["ready_node_ids"])

    def test_transport_or_semantic_failure_holds_promotion(self):
        transport = ProviderObservationCanary().run(
            self.observation(transport_ok=False)
        )
        semantic = ProviderObservationCanary().run(
            self.observation(semantic_match=False)
        )
        self.assertEqual(transport["status"], "HOLD")
        self.assertEqual(semantic["status"], "HOLD")

    def test_external_effect_is_rejected(self):
        with self.assertRaises(ValueError):
            ProviderObservationCanary().run(self.observation(external_effect=True))

    def test_raw_object_identifier_is_not_accepted_as_fingerprint(self):
        with self.assertRaises(ValueError):
            ProviderObservationCanary().run(
                self.observation(object_fingerprint="gmail-message-id")
            )


if __name__ == "__main__":
    unittest.main()
