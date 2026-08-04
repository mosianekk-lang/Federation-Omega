from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentGovernanceContractTests(unittest.TestCase):
    def test_root_agent_contract_contains_non_negotiable_controls(self) -> None:
        contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        required = (
            "Never commit or push directly to `main`.",
            "New workflows are default-deny.",
            "Do not commit generated runtime receipts",
            "require exact provider readback",
            "fully preventative only when GitHub platform rulesets require",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract)

    def test_copilot_instructions_bind_to_root_contract(self) -> None:
        instructions = (
            ROOT / ".github" / "copilot-instructions.md"
        ).read_text(encoding="utf-8")
        required = (
            "Follow the root `AGENTS.md` governance contract",
            "commit or push directly to `main`",
            "Runtime outputs belong in immutable artifacts",
            "merge-result readback",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, instructions)

    def test_contract_does_not_claim_platform_enforcement(self) -> None:
        contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("provider protection is not yet active", (
            ROOT / ".github" / "copilot-instructions.md"
        ).read_text(encoding="utf-8"))
        self.assertNotIn("branch protection is active", contract.lower())


if __name__ == "__main__":
    unittest.main()
