import json
from pathlib import Path
import unittest


WORKFLOW_PATH = '.github/workflows/google-ai-studio-semantic-canary-v1.yml'


class GoogleAIStudioSemanticCanaryV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path(WORKFLOW_PATH).read_text(encoding='utf-8')
        cls.contract = json.loads(Path('governance/google_ai_studio_semantic_canary_v1.json').read_text(encoding='utf-8'))
        cls.policy = json.loads(Path('governance/github_airlock_policy.json').read_text(encoding='utf-8'))

    def test_owner_only_exact_issue_gate(self) -> None:
        self.assertIn("[BUBBLES-PROBE] GOOGLE_AI_STUDIO_SEMANTIC_CANARY_V1", self.workflow)
        self.assertIn("author_association == 'OWNER'", self.workflow)

    def test_reuses_canonical_keyless_wif(self) -> None:
        self.assertIn('github-federation-omega/providers/github', self.workflow)
        self.assertIn('superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com', self.workflow)
        self.assertIn('id-token: write', self.workflow)

    def test_secret_is_transient_and_redacted(self) -> None:
        self.assertIn("'gcloud', 'secrets', 'versions', 'access', 'latest'", self.workflow)
        self.assertIn("'secret_value_recorded': False", self.workflow)
        self.assertNotIn("'api_key': api_key", self.workflow)
        self.assertNotIn('print(api_key)', self.workflow)
        self.assertEqual(self.contract['credential_handling']['access'], 'TRANSIENT_RUNNER_MEMORY_ONLY')
        self.assertFalse(self.contract['credential_handling']['log_recording'])
        self.assertFalse(self.contract['credential_handling']['receipt_recording'])

    def test_semantic_readback_is_exact_and_non_mutating(self) -> None:
        self.assertIn('generativelanguage.googleapis.com/v1beta/models', self.workflow)
        self.assertIn(':generateContent', self.workflow)
        self.assertIn('text == challenge', self.workflow)
        self.assertIn("'provider_mutation_attempted': False", self.workflow)
        for forbidden in ('gcloud run deploy', 'gcloud services enable', 'gcloud iam', 'git push', 'git commit'):
            self.assertNotIn(forbidden, self.workflow)

    def test_airlock_scope_is_exact(self) -> None:
        self.assertIn(WORKFLOW_PATH, self.policy['active_workflow_allowlist'])
        self.assertEqual(self.policy['allowed_events'][WORKFLOW_PATH], ['issues'])
        self.assertIn(WORKFLOW_PATH, self.policy['oidc_workflow_allowlist'])
        self.assertIn(WORKFLOW_PATH, self.policy['execution_quarantine']['keep_active'])
        self.assertNotIn(WORKFLOW_PATH, self.policy['provider_mutation_workflow_allowlist'])
        self.assertNotIn(WORKFLOW_PATH, self.policy['actions_write_workflow_allowlist'])
        self.assertNotIn(WORKFLOW_PATH, self.policy['statuses_write_workflow_allowlist'])


if __name__ == '__main__':
    unittest.main()
