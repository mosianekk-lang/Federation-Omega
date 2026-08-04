from __future__ import annotations

import json
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
            "Every material runtime or tool path must emit a terminal `SUCCESS`, `FAILURE` or `CONSTRAINT` event",
            "A repeated failure fingerprint must open the affected circuit",
            "Generated learning ledgers and trigger-state artifacts must not be committed to canonical source",
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
            "append-only learning ledger",
            "without recording its success, failure or constraint",
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

    def test_learning_policy_is_fail_closed(self) -> None:
        policy = json.loads(
            (
                ROOT / "governance" / "federation_learning_policy.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            "FEDOMEGA-CONTINUOUS-LEARNING-TRIGGERS-V1",
            policy["policy_id"],
        )
        self.assertEqual("A1_INTERNAL", policy["authority_ceiling"])
        self.assertFalse(policy["external_effect"])
        self.assertEqual(
            "FORBIDDEN", policy["source_repository_runtime_output"]
        )
        controls = set(policy["non_negotiable_controls"])
        self.assertIn("NO_AUTHORITY_EXPANSION_FROM_LEARNING", controls)
        self.assertIn("NO_TRUST_TRANSFER_BETWEEN_WORKFLOWS", controls)
        self.assertIn("NO_RUNTIME_RECEIPTS_IN_CANONICAL_SOURCE", controls)


if __name__ == "__main__":
    unittest.main()
