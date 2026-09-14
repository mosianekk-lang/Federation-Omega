from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "seb-omega.yml"
PROOF = ROOT / "sovereign_execution_boundary" / "prove_openrouter_zero_cost.py"


class SebOmegaOptionalOpenRouterGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.proof = PROOF.read_text(encoding="utf-8")

    def test_provider_canary_requires_explicit_dispatch(self) -> None:
        marker = "  zero-traffic-canary:\n"
        self.assertIn(marker, self.workflow)
        canary = self.workflow.split(marker, 1)[1]
        self.assertIn("    if: github.event_name == 'workflow_dispatch'\n", canary)
        self.assertNotIn(
            "    if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'\n",
            canary,
        )

    def test_main_push_keeps_source_qualification_but_not_provider_canary(self) -> None:
        self.assertIn("  push:\n    branches: [main]\n", self.workflow)
        self.assertIn("  qualify:\n", self.workflow)
        self.assertIn("      - run: python -m unittest discover -s tests -v\n", self.workflow)

    def test_explicit_canary_remains_fail_closed_and_private(self) -> None:
        self.assertIn("OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", self.workflow)
        self.assertIn("DEPLOY_SEB_OMEGA_ZERO_TRAFFIC", self.workflow)
        self.assertIn("--no-allow-unauthenticated", self.workflow)
        self.assertIn("id-token: write", self.workflow)
        self.assertIn('raise RuntimeError("OPENROUTER_API_KEY is not bound")', self.proof)


if __name__ == "__main__":
    unittest.main()
