from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "federation_n_directive_v2.yaml"
BOOTSTRAP = ROOT / "governance" / "federation_node_bootstrap_v2.json"


class FederationNDirectiveV2Tests(unittest.TestCase):
    def test_policy_contains_monotonic_continuation_contract(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        required = (
            "policy_id: FEDOMEGA-N-DIRECTIVE-V2",
            "input: n",
            "close the current critical dependency",
            "begin the next justified advancement",
            "continue without status-only pauses",
            "explicit reusable continuation line: n = proceed",
            "record terminal SUCCESS, FAILURE or CONSTRAINT",
            "future_nodes:",
            "mandatory at node creation or registration before substantive work",
            "authority_ceiling: A1_INTERNAL",
            "external_effect_default: false",
            "no invisible access to closed or unrelated chats is claimed",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_future_node_bootstrap_is_fail_closed(self) -> None:
        bootstrap = json.loads(BOOTSTRAP.read_text(encoding="utf-8"))
        self.assertTrue(bootstrap["required_before_substantive_work"])
        self.assertIn(
            "FEDOMEGA-N-DIRECTIVE-V2", bootstrap["inherited_policies"]
        )
        self.assertEqual(
            "n = proceed", bootstrap["output_contract"]["explicit_continuation_line"]
        )
        self.assertTrue(
            bootstrap["output_contract"]["complete_next_best_automated_pathway"]
        )
        self.assertFalse(
            bootstrap["output_contract"]["status_only_closure_with_safe_work"]
        )
        self.assertEqual("A1_INTERNAL", bootstrap["authority"]["ceiling"])
        self.assertFalse(bootstrap["authority"]["external_effect_default"])
        self.assertFalse(bootstrap["authority"]["trust_inheritance"])
        self.assertEqual(
            "BOOTSTRAP_BLOCKED_FAIL_CLOSED", bootstrap["failure_state"]
        )

    def test_governance_contracts_bind_the_policy(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        copilot = (
            ROOT / ".github" / "copilot-instructions.md"
        ).read_text(encoding="utf-8")
        for text in (agents, copilot):
            self.assertIn("FEDOMEGA-N-DIRECTIVE-V2", text)
            self.assertIn("n = proceed", text)
            self.assertIn("complete next-best automated pathway", text)

    def test_policy_does_not_expand_consequential_authority(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        held = (
            "external communications",
            "legal filing",
            "payments and financial commitments",
            "evidence deletion or mutation",
            "material production deployment",
            "authority expansion",
            "trust transfer",
        )
        for phrase in held:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, policy)


if __name__ == "__main__":
    unittest.main()
