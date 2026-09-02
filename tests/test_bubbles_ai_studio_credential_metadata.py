from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "bubbles-provider-authority-recovery-probe.yml"


class BubblesAIStudioCredentialMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW.exists():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_qualification_reuses_existing_authority_probe(self) -> None:
        self.assertIn("name: Bubbles Provider Authority Recovery Probe", self.workflow)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", self.workflow)
        self.assertIn("WIF_PROVIDER:", self.workflow)

    def test_gemini_secret_qualification_is_metadata_only(self) -> None:
        self.assertIn("'gemini-api-key'", self.workflow)
        self.assertIn("'secrets','describe','gemini-api-key'", self.workflow)
        self.assertIn("'secrets','versions','list','gemini-api-key'", self.workflow)
        self.assertNotIn("'secrets','versions','access','latest','--secret=gemini-api-key'", self.workflow)
        self.assertNotIn("generativelanguage.googleapis.com", self.workflow)
        self.assertNotIn("generateContent", self.workflow)

    def test_receipt_preserves_no_effect_truth_boundary(self) -> None:
        self.assertIn("'gemini_ai_studio_credential'", self.workflow)
        self.assertIn("'secret_value_accessed':False", self.workflow)
        self.assertIn("'provider_call_performed':False", self.workflow)
        self.assertIn("'secret_values_recorded':False", self.workflow)
        self.assertIn("'mutation_attempted':False", self.workflow)
        self.assertIn("No Gemini Developer API call", self.workflow)


if __name__ == "__main__":
    unittest.main()
