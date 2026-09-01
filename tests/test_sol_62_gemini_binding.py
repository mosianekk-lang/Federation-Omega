from __future__ import annotations

import unittest

from sol_61_runtime.sol_62_gemini_binding import (
    ConnectionLevel,
    GeminiBindingError,
    load_binding,
)


class Sol62GeminiBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.binding = load_binding()

    def test_live_provider_proof_binds_control_plane(self) -> None:
        self.assertEqual(self.binding.workflow_run_id, "33465835354")
        self.assertEqual(self.binding.source_sha, "4381762481262321f712d71c1c09d9f530e04a7d")
        self.assertEqual(self.binding.project_id, "sov-hybrid-suite")
        self.assertTrue(self.binding.oidc_exchange_succeeded)
        self.assertTrue(self.binding.adc_verified)
        self.assertTrue(self.binding.control_plane_connected)
        self.assertEqual(self.binding.connection_level, ConnectionLevel.CONTROL_PLANE_AUTHENTICATED)

    def test_inference_is_held_until_hardened_wif_and_provider_receipt(self) -> None:
        self.assertFalse(self.binding.hardened_wif_contract_verified)
        self.assertFalse(self.binding.model_inference_performed)
        self.assertFalse(self.binding.inference_ready)
        with self.assertRaisesRegex(GeminiBindingError, "hardened WIF"):
            self.binding.assert_inference_ready()

    def test_only_read_only_capabilities_are_admitted(self) -> None:
        for capability in (
            "READ_PROJECT_METADATA",
            "READ_WIF_PROVIDER_METADATA",
            "VERIFY_ADC_RUNTIME_IDENTITY",
            "READ_GEMINI_AUTHORITY_STATE",
        ):
            self.binding.assert_capability(capability)
        for capability in ("MODEL_INFERENCE", "PROVIDER_MUTATION", "DEPLOYMENT"):
            with self.assertRaises(GeminiBindingError):
                self.binding.assert_capability(capability)

    def test_connection_does_not_hide_provider_effects_or_secret_access(self) -> None:
        self.assertFalse(self.binding.provider_mutation_performed)
        self.assertFalse(self.binding.secret_payload_accessed)
        receipt = self.binding.receipt()
        self.assertTrue(receipt["control_plane_connected"])
        self.assertFalse(receipt["inference_ready"])
        self.assertEqual(len(receipt["receipt_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
