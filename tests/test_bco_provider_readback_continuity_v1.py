import tempfile
import unittest

from benchmarking.cfbe_omega.bco_provider_readback_continuity_v1 import prepare, resume_and_bind


class BCOProviderReadbackContinuityTests(unittest.TestCase):
    HEAD = "a" * 40

    def _public_receipt(self):
        return {
            "schema": "BUBBLES-PROVIDER-SURFACE-PROBE-V1",
            "mutation_attempted": False,
            "secret_values_recorded": False,
            "surfaces": {
                "federation_omega_operator": {
                    "classification": "BLOCKED_TRUSTED_TOKEN_BINDING",
                    "public_health": {"http_status": 200, "body": {"ok": True}},
                    "public_contract": {"http_status": 200, "body": {"ok": True}},
                    "authenticated_status": None,
                    "authenticated_cloud_read": None,
                }
            },
        }

    def _authenticated_receipt(self):
        return {
            "schema": "BUBBLES-PROVIDER-SURFACE-PROBE-V1",
            "mutation_attempted": False,
            "secret_values_recorded": False,
            "surfaces": {
                "federation_omega_operator": {
                    "classification": "AUTHENTICATED_READBACK_VERIFIED",
                    "public_health": {"http_status": 200, "body": {"ok": True}},
                    "public_contract": {"http_status": 200, "body": {"ok": True}},
                    "authenticated_status": {"http_status": 200, "body": {"ok": True}},
                    "authenticated_cloud_read": {"http_status": 200, "body": {"ok": True, "mutation": "NONE"}},
                }
            },
        }

    def test_public_receipt_survives_restart_but_keeps_request_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = prepare(tmp, head_sha=self.HEAD, created_at="2026-08-31T23:00:00+02:00")
            self.assertEqual("PREPARED_PENDING_PROVIDER_RECEIPT", first["state"])
            second = resume_and_bind(
                tmp,
                head_sha=self.HEAD,
                receipt=self._public_receipt(),
                receipt_ref="artifact:public-provider-receipt",
                now="2026-08-31T23:01:00+02:00",
            )
            self.assertEqual("RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", second.resume_state)
            self.assertEqual("HOLD_PROVIDER_READBACK_FLOOR_UNMET", second.state)
            self.assertEqual("PUBLIC_REACHABILITY", second.observed_level)
            self.assertEqual("PENDING", second.request_state)
            self.assertEqual(1, second.pending_request_count)
            self.assertEqual("PLANNED", second.work_state)
            self.assertFalse(second.provider_effect_authorized)

    def test_authenticated_action_receipt_resolves_after_restart_without_effect_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            prepare(tmp, head_sha=self.HEAD, created_at="2026-08-31T23:00:00+02:00")
            second = resume_and_bind(
                tmp,
                head_sha=self.HEAD,
                receipt=self._authenticated_receipt(),
                receipt_ref="artifact:authenticated-provider-receipt",
                now="2026-08-31T23:01:00+02:00",
            )
            self.assertEqual("RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", second.resume_state)
            self.assertEqual("PROVIDER_READBACK_BOUND", second.state)
            self.assertEqual("ACTION_SPECIFIC_AUTHENTICATED_READ", second.observed_level)
            self.assertEqual("RESOLVED", second.request_state)
            self.assertEqual(0, second.pending_request_count)
            self.assertEqual("VERIFIED", second.work_state)
            self.assertFalse(second.provider_effect_authorized)


if __name__ == "__main__":
    unittest.main()
