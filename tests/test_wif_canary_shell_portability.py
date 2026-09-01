from __future__ import annotations

import unittest
from pathlib import Path


class WifCanaryShellPortabilityTests(unittest.TestCase):
    def test_v2_canary_invokes_repository_read_only_plans_through_bash(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow_file = root / ".github/workflows/fo-wif-semantic-canary-v2.yml"
        if not workflow_file.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        workflow = workflow_file.read_text(encoding="utf-8")
        self.assertIn("bash ./ops/bootstrap_github_wif.sh --plan", workflow)
        self.assertIn("bash ./ops/bootstrap_gemini_gateway.sh --plan", workflow)
        self.assertNotIn("\n          ./ops/bootstrap_github_wif.sh --plan", workflow)
        self.assertNotIn("\n          ./ops/bootstrap_gemini_gateway.sh --plan", workflow)
        self.assertIn("assert p['mutation_performed'] is False", workflow)
        self.assertIn("assert plan['mutation_performed'] is False", workflow)
        self.assertIn("'provider_effect_executed':False", workflow)


if __name__ == "__main__":
    unittest.main()
