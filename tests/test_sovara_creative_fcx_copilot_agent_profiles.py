import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".github" / "agents"
GOVERNANCE = ROOT / "governance" / "sovara_fcx_copilot_pro_adapter_v1.json"


class FCXCopilotAgentProfileTests(unittest.TestCase):
    def test_all_four_native_custom_agent_profiles_exist(self):
        expected = {
            "fcx-builder.agent.md",
            "fcx-reviewer.agent.md",
            "fcx-falsifier.agent.md",
            "fcx-gemini-challenger.agent.md",
        }
        observed = {path.name for path in AGENTS_DIR.glob("fcx-*.agent.md")}
        self.assertEqual(observed, expected)

    def test_profiles_use_required_github_frontmatter(self):
        for path in AGENTS_DIR.glob("fcx-*.agent.md"):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path.name)
            self.assertIn("\ndescription:", text, path.name)
            self.assertIn("\ntarget: github-copilot\n", text, path.name)
            self.assertIn("AGENTS.md", text, path.name)
            self.assertIn(".github/copilot-instructions.md", text, path.name)

    def test_builder_is_branch_pr_only(self):
        text = (AGENTS_DIR / "fcx-builder.agent.md").read_text(encoding="utf-8")
        self.assertIn("purpose-specific branch", text)
        self.assertIn("pull request", text)
        self.assertIn("Never push or commit directly to `main`", text)

    def test_review_falsifier_and_gemini_profiles_are_read_only(self):
        for name in (
            "fcx-reviewer.agent.md",
            "fcx-falsifier.agent.md",
            "fcx-gemini-challenger.agent.md",
        ):
            text = (AGENTS_DIR / name).read_text(encoding="utf-8")
            self.assertIn("read-only", text, name)

    def test_gemini_profile_does_not_self_assert_model_identity(self):
        text = (AGENTS_DIR / "fcx-gemini-challenger.agent.md").read_text(encoding="utf-8")
        self.assertIn("Never infer that you are Gemini", text)
        self.assertIn("UNVERIFIED", text)
        self.assertIn("proposal-only", text)

    def test_governance_keeps_paid_overage_and_mcp_fail_closed(self):
        payload = json.loads(GOVERNANCE.read_text(encoding="utf-8"))
        self.assertEqual(payload["credit_policy"]["paid_overage_default"], "DENY")
        self.assertEqual(
            payload["custom_agent_contract"]["mcp"],
            "HELD_FOR_SEPARATE_DATA_MINIMIZATION_AND_TRUST_CANARY",
        )
        self.assertEqual(payload["promotion_ceiling"], "SOURCE_CANDIDATE")

    def test_private_entitlement_is_not_committed_to_public_source(self):
        payload = json.loads(GOVERNANCE.read_text(encoding="utf-8"))
        self.assertEqual(payload["account_entitlement"], "PRIVATE_ACCOUNT_EVIDENCE_REQUIRED")
        public_text = GOVERNANCE.read_text(encoding="utf-8")
        self.assertNotIn("mosianekk@gmail.com", public_text)
        self.assertNotIn("MasterCard", public_text)


if __name__ == "__main__":
    unittest.main()
