import unittest

from ops.sovara_provider_recovery_controller import build_recovery_receipt


class SovaraProviderRecoveryControllerTests(unittest.TestCase):
    def test_google_invalid_target_opens_circuit(self):
        receipt = build_recovery_receipt({
            "google": {
                "wif_exchange_error": "invalid_target",
                "closure": {"canonical_wif_authenticated": False},
            }
        })
        lane = receipt["lanes"]["google"]
        self.assertEqual("AUTHENTICATED_ADMIN_REPAIR_REQUIRED", lane["state"])
        self.assertEqual("OPEN_UNCHANGED_WIF_RETRY", lane["circuit"])
        self.assertIn("FRESH_WIF_TOKEN_ISSUED", lane["auto_continue_on"])

    def test_openai_credit_exhaustion_preserves_verified_model_visibility(self):
        receipt = build_recovery_receipt({
            "openai": {
                "closure": {
                    "openai_api_authority_bound": True,
                    "gpt56_model_resource_verified": True,
                    "gpt56_provider_response_created": False,
                    "gpt56_semantic_readback_verified": False,
                },
                "attempts": [{
                    "requested_model": "gpt-5.6-sol",
                    "model_resource_http": 200,
                    "create_http": 429,
                    "create_error_type": "insufficient_quota",
                    "create_error_code": "credit_balance_exhausted",
                }],
            }
        })
        lane = receipt["lanes"]["openai"]
        self.assertEqual("CREDIT_RECOVERY_REQUIRED", lane["state"])
        self.assertIn("GPT56_MODEL_RESOURCE", lane["proof"])
        self.assertEqual("OPEN_PAID_INFERENCE_RETRY", lane["circuit"])

    def test_openrouter_catalog_without_runtime_key_routes_to_secure_binding(self):
        receipt = build_recovery_receipt({
            "openrouter": {
                "api_key_bound": False,
                "gpt56_catalog_present": True,
                "models_http": 200,
            }
        })
        lane = receipt["lanes"]["openrouter"]
        self.assertEqual("SECURE_KEY_BINDING_REQUIRED", lane["state"])
        self.assertIn("PUBLIC_GPT56_CATALOG", lane["proof"])

    def test_google_repair_wins_route_tournament_for_current_failure_shape(self):
        receipt = build_recovery_receipt({
            "google": {"wif_exchange_error": "invalid_target"},
            "openai": {
                "api_key_present": True,
                "closure": {"gpt56_model_resource_verified": True},
                "attempts": [{"create_error_type": "insufficient_quota"}],
            },
            "openrouter": {"gpt56_catalog_present": True, "api_key_bound": False},
        })
        selected = receipt["route_tournament"]["selected"]
        self.assertEqual("REUSE_OPTIMISE", selected["family"])
        self.assertIn("Google WIF", selected["route"])

    def test_verified_lane_does_not_wait_for_other_lanes(self):
        receipt = build_recovery_receipt({
            "google": {
                "closure": {
                    "canonical_wif_authenticated": True,
                    "google_cloud_readback_verified": True,
                    "operator_authenticated_readback_verified": True,
                    "gemini_semantic_readback_verified": True,
                }
            },
            "openai": {},
            "openrouter": {},
        })
        self.assertEqual("VERIFIED", receipt["lanes"]["google"]["state"])
        self.assertNotIn("google", receipt["blocked_lanes"])
        self.assertTrue(receipt["execution_policy"]["independent_lanes_continue"])

    def test_recovery_controller_never_performs_provider_effects(self):
        receipt = build_recovery_receipt({})
        policy = receipt["execution_policy"]
        self.assertFalse(policy["provider_effect_performed_by_controller"])
        self.assertFalse(policy["paid_inference_performed_by_controller"])
        self.assertFalse(policy["secret_values_accepted"])

    def test_failure_fingerprint_is_stable(self):
        first = build_recovery_receipt({"google": {"wif_exchange_error": "invalid_target"}})
        second = build_recovery_receipt({"google": {"wif_exchange_error": "invalid_target"}})
        self.assertEqual(
            first["lanes"]["google"]["failure_fingerprint"],
            second["lanes"]["google"]["failure_fingerprint"],
        )

    def test_secret_like_material_is_rejected(self):
        with self.assertRaises(ValueError):
            build_recovery_receipt({"openai": {"raw": "sk-proj-1234567890abcdefghijklmnop"}})


if __name__ == "__main__":
    unittest.main()
