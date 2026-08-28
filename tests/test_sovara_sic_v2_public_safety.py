import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ops" / "sovara_sovereign_intelligence_court_v2.py"
PROVIDER = ROOT / "ops" / "sovara_openrouter_code_eval_v1.py"
WORKFLOW = ROOT / ".github" / "workflows" / "sovara-sovereign-intelligence-court-v2.yml"


class SovaraSICV2PublicSafetyTests(unittest.TestCase):
    def test_provider_key_is_runtime_reference_not_literal(self):
        text = PROVIDER.read_text(encoding="utf-8") + CORE.read_text(encoding="utf-8")
        self.assertIn('os.environ.get("OPENROUTER_API_KEY"', text)
        self.assertIsNone(re.search(r"sk-or-v1-[A-Za-z0-9_-]{20,}", text))

    def test_external_model_outputs_are_proposal_only_and_non_mutating(self):
        core = CORE.read_text(encoding="utf-8")
        self.assertIn('"canonical_source_modified": False', core)
        self.assertIn('"promotion_allowed": False', core)
        self.assertNotIn("git push", core)
        self.assertNotIn("subprocess.run", core)

    def test_workflow_is_least_privilege_and_not_manually_dispatchable(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("workflow_dispatch:", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("actions: write", workflow)

    def test_secret_shaped_source_has_external_transmission_gate(self):
        core = CORE.read_text(encoding="utf-8")
        self.assertIn("BLOCK_EXTERNAL_TRANSMISSION", core)
        self.assertIn("external_transmission_allowed", core)
        self.assertIn("PRIVACY_BOUNDARY", core)


if __name__ == "__main__":
    unittest.main()
