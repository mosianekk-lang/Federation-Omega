from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SovaraGoogleInteractionsV2CanaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (
            ROOT / ".github" / "workflows" / "sovara-ai-studio-semantic-canary.yml"
        ).read_text(encoding="utf-8")
        cls.runner = (
            ROOT / "scripts" / "run_google_interactions_v2_canary.py"
        ).read_text(encoding="utf-8")

    def test_reuses_approved_keyless_gateway(self) -> None:
        self.assertIn("id-token: write", self.workflow)
        self.assertIn("google-github-actions/auth@", self.workflow)
        self.assertIn("Run V2 Gemini 3.8 Interactions semantic canary", self.workflow)
        self.assertIn("python3 scripts/run_google_interactions_v2_canary.py", self.workflow)
        self.assertIn('branches: ["main"]', self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)

    def test_runner_is_stateless_and_targets_interactions(self) -> None:
        self.assertIn('"store": False', self.runner)
        self.assertIn("gemini-3.8-flash", self.runner)
        self.assertIn("/locations/{location}/interactions", self.runner)
        self.assertIn("VERTEX_AI_INTERACTIONS_REST", self.runner)
        self.assertIn("interaction_id", self.runner)
        self.assertIn("interaction_status", self.runner)
        self.assertIn("semantic_verified", self.runner)
        self.assertNotIn("GEMINI_API_KEY", self.runner)

    def test_runner_declares_zero_external_effects(self) -> None:
        for marker in (
            '"provider_mutation_performed": False',
            '"iam_mutation_performed": False',
            '"secret_value_recorded": False',
            '"deployment_performed": False',
            '"traffic_change_performed": False',
            '"external_communication_performed": False',
        ):
            self.assertIn(marker, self.runner)

    def test_v2_semantic_canary_runs_before_legacy_performance_court(self) -> None:
        v2_index = self.workflow.index("Run V2 Gemini 3.8 Interactions semantic canary")
        legacy_index = self.workflow.index("Run bounded portable reasoning role matrix")
        self.assertLess(v2_index, legacy_index)

    def test_interactions_receipt_upload_is_immutable_artifact(self) -> None:
        self.assertIn("Upload immutable redacted V2 Interactions receipt", self.workflow)
        self.assertIn("INTERACTIONS_V2_SEMANTIC_RECEIPT.json", self.workflow)
        self.assertIn("retention-days: 90", self.workflow)


if __name__ == "__main__":
    unittest.main()
