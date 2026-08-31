from __future__ import annotations

import unittest
from pathlib import Path


class WifCanaryShellPortabilityTests(unittest.TestCase):
    def test_v2_canary_invokes_repository_shell_verifiers_through_bash(self) -> None:
        root = Path(__file__).resolve().parents[1]
        workflow_file = root / ".github/workflows/fo-wif-semantic-canary-v2.yml"
        if not workflow_file.exists():
            self.skipTest("workflow-free export excludes repository workflow controls")
        workflow = workflow_file.read_text(encoding="utf-8")
        self.assertIn("bash ./ops/bootstrap_github_wif.sh --verify", workflow)
        self.assertIn("bash ./ops/bootstrap_gemini_gateway.sh --verify", workflow)
        self.assertNotIn("\n          ./ops/bootstrap_github_wif.sh --verify", workflow)
        self.assertNotIn("\n          ./ops/bootstrap_gemini_gateway.sh --verify", workflow)


if __name__ == "__main__":
    unittest.main()
