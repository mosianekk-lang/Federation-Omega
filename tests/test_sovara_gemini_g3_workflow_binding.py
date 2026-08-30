from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "sovara-litellm-v2-3-provider-admission.yml"


class SovaraGeminiG3WorkflowBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_g3_is_additive_supported_mode_with_exact_private_scope(self) -> None:
        self.assertIn("mode == 'G3_PRIVATE_GATEWAY_CANARY'", self.workflow)
        self.assertIn("PRIVATE_ZERO_TRAFFIC_CANARY", self.workflow)
        self.assertIn("production_traffic_allowed') is False", self.workflow)
        self.assertIn("superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com", self.workflow)
        self.assertIn("p.get('service') == 'sovara-gemini-gateway'", self.workflow)

    def test_g3_reuses_exact_trusted_workflow_and_verified_adc_gate(self) -> None:
        self.assertIn("G0_READ_ONLY_VERIFY|G3_PRIVATE_GATEWAY_CANARY|FULL_PROVIDER_ADMISSION", self.workflow)
        self.assertIn("./sovara/gemini/private_gateway_canary.sh --execute", self.workflow)
        self.assertIn("DEPLOY_PRIVATE_ZERO_TRAFFIC_GEMINI_CANARY_V1", self.workflow)
        self.assertIn("G3_EXIT_CODE", self.workflow)

    def test_g3_has_independent_truth_receipt_and_enforcement(self) -> None:
        for needle in (
            "G3_PRIVATE_CANARY_RECEIPT.json",
            "FEDOMEGA-GEMINI-GATEWAY-CANARY-VERIFIED",
            "gemini_private_canary_verified",
            "gemini_private_canary_normal_traffic_percent",
            "production_promotion_performed",
            "G3 private Gemini gateway canary verified",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.workflow)
        self.assertIn(".gemini_private_canary_normal_traffic_percent == 0", self.workflow)
        self.assertIn(".production_promotion_performed == false", self.workflow)

    def test_g3_does_not_reuse_full_provider_admission_executor(self) -> None:
        g3_block = self.workflow.split("- name: Execute private zero-traffic Gemini gateway canary", 1)[1].split(
            "- name: Execute provider admission, canaries, deployment, and rollback gates", 1
        )[0]
        self.assertIn("if: steps.provider_mode.outputs.scope == 'G3_PRIVATE_GATEWAY_CANARY'", g3_block)
        self.assertIn("private_gateway_canary.sh", g3_block)
        self.assertNotIn("run_provider_admission_v2_3.sh", g3_block)
        self.assertNotIn("update-traffic", g3_block)

    def test_g2_and_g3_execution_lanes_remain_exactly_separate(self) -> None:
        g2_block = self.workflow.split("- name: Execute bounded Gemini Creative Architecture Challenge", 1)[1].split(
            "- name: Execute private zero-traffic Gemini gateway canary", 1
        )[0]
        g3_block = self.workflow.split("- name: Execute private zero-traffic Gemini gateway canary", 1)[1].split(
            "- name: Execute provider admission, canaries, deployment, and rollback gates", 1
        )[0]
        self.assertIn("if: steps.provider_mode.outputs.scope == 'G2_CREATIVE_ARCHITECTURE_CHALLENGE'", g2_block)
        self.assertIn("gemini_architecture_challenge.py", g2_block)
        self.assertNotIn("private_gateway_canary.sh", g2_block)
        self.assertIn("if: steps.provider_mode.outputs.scope == 'G3_PRIVATE_GATEWAY_CANARY'", g3_block)
        self.assertIn("private_gateway_canary.sh", g3_block)
        self.assertNotIn("gemini_architecture_challenge.py", g3_block)

    def test_existing_modes_are_preserved(self) -> None:
        for mode in (
            "G0_READ_ONLY_VERIFY",
            "G1_ADC_APPLY_VERIFY",
            "G2_CREATIVE_ARCHITECTURE_CHALLENGE",
            "G3_PRIVATE_GATEWAY_CANARY",
            "FULL_PROVIDER_ADMISSION",
            "SOURCE_VALIDATION_ONLY",
        ):
            with self.subTest(mode=mode):
                self.assertIn(mode, self.workflow)


if __name__ == "__main__":
    unittest.main()
