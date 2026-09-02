from pathlib import Path
import unittest


WORKFLOW = Path('.github/workflows/google-ai-studio-semantic-canary-v1.yml')


class GoogleAIStudioSemanticCanaryV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding='utf-8')

    def test_owner_only_exact_issue_gate(self) -> None:
        self.assertIn("[BUBBLES-PROBE] GOOGLE_AI_STUDIO_SEMANTIC_CANARY_V1", self.workflow)
        self.assertIn("author_association == 'OWNER'", self.workflow)

    def test_uses_existing_keyless_wif(self) -> None:
        self.assertIn('github-federation-omega/providers/github', self.workflow)
        self.assertIn('superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com', self.workflow)
        self.assertIn('id-token: write', self.workflow)

    def test_secret_is_transient_and_receipt_is_redacted(self) -> None:
        self.assertIn("'gcloud', 'secrets', 'versions', 'access', 'latest'", self.workflow)
        self.assertIn("'secret_value_recorded': False", self.workflow)
        self.assertNotIn('echo "$api_key"', self.workflow)
        self.assertNotIn('print(api_key)', self.workflow)

    def test_provider_call_is_semantic_not_mutating(self) -> None:
        self.assertIn('generativelanguage.googleapis.com/v1beta/models', self.workflow)
        self.assertIn(':generateContent', self.workflow)
        self.assertIn("'provider_mutation_attempted': False", self.workflow)
        for forbidden in ('gcloud run deploy', 'gcloud services enable', 'gcloud iam', 'git push', 'git commit'):
            self.assertNotIn(forbidden, self.workflow)

    def test_semantic_proof_is_exact_and_artifact_only(self) -> None:
        self.assertIn("'GEMINI_SEMANTIC_READBACK_PROVEN'", self.workflow)
        self.assertIn("text == challenge", self.workflow)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02', self.workflow)


if __name__ == '__main__':
    unittest.main()
