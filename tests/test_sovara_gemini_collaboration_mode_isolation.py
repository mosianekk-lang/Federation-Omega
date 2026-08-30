from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / "governance" / "sovara_gemini_collaboration_request_v1.json"
CHALLENGE = ROOT / "governance" / "sovara_creative_gemini_architecture_challenge_v1.json"


class SovaraGeminiCollaborationModeIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.active = json.loads(ACTIVE.read_text(encoding="utf-8"))
        self.challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))

    def test_active_request_remains_stable_g0_control_surface(self) -> None:
        self.assertEqual("G0_READ_ONLY_VERIFY", self.active["mode"])
        self.assertEqual("ADMIN_AUTHORITY_GRAPH_CENSUS", self.active["g0_objective"])
        self.assertTrue(self.active["deployment_readiness_probe"])
        self.assertFalse(self.active["provider_mutation_allowed"])
        self.assertFalse(self.active["model_inference_allowed"])
        self.assertFalse(self.active["external_communication_allowed"])
        self.assertFalse(self.active["promote"])
        self.assertEqual(
            {
                "aiplatform_user_binding",
                "service_usage_consumer_binding",
                "deployer_cloud_run_developer_binding",
            },
            set(self.active["expected_missing_adc_controls"]),
        )

    def test_proposal_only_g2_challenge_is_separate_evidence_not_active_mode(self) -> None:
        self.assertEqual("CFBE-GEMINI-REPAIR-20260830-001", self.challenge["challenge_id"])
        self.assertEqual("google/gemini-3.1-pro-preview", self.challenge["model"])
        self.assertTrue(self.challenge["sanitized"])
        self.assertFalse(self.challenge["case_data_allowed"])
        self.assertFalse(self.challenge["external_effect_allowed"])
        self.assertNotEqual(self.challenge["challenge_id"], self.active["request_id"])
        self.assertNotIn("challenge_spec", self.active)
        self.assertNotIn("transport", self.active)

    def test_one_off_challenge_cannot_expand_active_request_authority(self) -> None:
        self.assertEqual(
            ".github/workflows/sovara-litellm-v2-3-provider-admission.yml",
            self.active["expected_workflow"],
        )
        self.assertTrue(self.active["deployment_readiness_scope"]["read_only"])
        self.assertIn("proposal-only", self.challenge["system_prompt"])
        self.assertIn("Never weaken safety", self.challenge["system_prompt"])


if __name__ == "__main__":
    unittest.main()
