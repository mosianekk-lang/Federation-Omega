from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "governance" / "sovara_gemini_g3_private_canary_request_template_v1.json"
ACTIVE = ROOT / "governance" / "sovara_gemini_collaboration_request_v1.json"


class SovaraGeminiG3RequestTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def test_template_matches_exact_trusted_g3_contract(self) -> None:
        p = self.template
        self.assertEqual("SOVARA_GEMINI_COLLABORATION_REQUEST_V1", p["schema"])
        self.assertEqual("G3_PRIVATE_GATEWAY_CANARY", p["mode"])
        self.assertTrue(p["execute"])
        self.assertFalse(p["promote"])
        self.assertFalse(p["case_data_allowed"])
        self.assertTrue(p["provider_mutation_allowed"])
        self.assertTrue(p["model_inference_allowed"])
        self.assertFalse(p["external_communication_allowed"])
        self.assertEqual("PRIVATE_ZERO_TRAFFIC_CANARY", p["deployment_scope"])
        self.assertFalse(p["production_traffic_allowed"])
        self.assertEqual(
            "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
            p["runtime_service_account"],
        )
        self.assertEqual("sovara-gemini-gateway", p["service"])

    def test_template_requires_adc_and_canary_receipt(self) -> None:
        self.assertIn("FEDOMEGA-GEMINI-ADC-VERIFIED", self.template["activation_preconditions"])
        self.assertEqual(
            "FEDOMEGA-GEMINI-GATEWAY-CANARY-VERIFIED",
            self.template["promotion_receipt_required"],
        )
        self.assertIn("production_traffic_promotion", self.template["forbidden_effects"])
        self.assertIn("public_unauthenticated_access", self.template["forbidden_effects"])

    def test_g3_template_is_separate_from_mutable_active_request(self) -> None:
        self.assertNotEqual(TEMPLATE, ACTIVE)
        self.assertTrue(TEMPLATE.name.endswith("_template_v1.json"))
        self.assertEqual("G3_PRIVATE_GATEWAY_CANARY", self.template["mode"])


if __name__ == "__main__":
    unittest.main()
