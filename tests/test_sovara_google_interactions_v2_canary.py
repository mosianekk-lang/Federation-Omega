from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SovaraGoogleInteractionsV2CanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (
            ROOT / ".github" / "workflows" / "sovara-google-interactions-v2-canary.yml"
        ).read_text(encoding="utf-8")

    def test_workflow_is_keyless_and_stateless(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("google-github-actions/auth@", self.workflow)
        self.assertIn("GITHUB_WIF_ADC", self.workflow)
        self.assertIn("'store': False", self.workflow)
        self.assertNotIn("GEMINI_API_KEY", self.workflow)

    def test_workflow_targets_interactions_and_gemini_38(self) -> None:
        self.assertIn("gemini-3.8-flash", self.workflow)
        self.assertIn("/locations/{location}/interactions", self.workflow)
        self.assertIn("VERTEX_AI_INTERACTIONS_REST", self.workflow)
        self.assertIn("interaction_id", self.workflow)
        self.assertIn("interaction_status", self.workflow)
        self.assertIn("semantic_verified", self.workflow)

    def test_workflow_declares_zero_external_effects(self) -> None:
        for marker in (
            "'provider_mutation_performed':False",
            "'iam_mutation_performed':False",
            "'secret_value_recorded':False",
            "'deployment_performed':False",
            "'traffic_change_performed':False",
            "'external_communication_performed':False",
        ):
            self.assertIn(marker, self.workflow)

    def test_workflow_is_main_or_manual_only(self) -> None:
        self.assertIn('branches: ["main"]', self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)


if __name__ == "__main__":
    unittest.main()
