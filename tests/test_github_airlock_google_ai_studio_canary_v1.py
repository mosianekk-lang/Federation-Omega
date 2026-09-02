import json
from pathlib import Path
import unittest


WORKFLOW = '.github/workflows/google-ai-studio-semantic-canary-v1.yml'


class GitHubAirlockGoogleAIStudioCanaryV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(Path('governance/github_airlock_policy.json').read_text(encoding='utf-8'))

    def test_workflow_is_explicitly_admitted(self) -> None:
        self.assertIn(WORKFLOW, self.policy['active_workflow_allowlist'])
        self.assertEqual(self.policy['allowed_events'][WORKFLOW], ['issues'])
        self.assertIn(WORKFLOW, self.policy['oidc_workflow_allowlist'])
        self.assertIn(WORKFLOW, self.policy['execution_quarantine']['keep_active'])

    def test_canary_is_not_provider_mutation_authorized(self) -> None:
        self.assertNotIn(WORKFLOW, self.policy['provider_mutation_workflow_allowlist'])
        self.assertNotIn(WORKFLOW, self.policy['actions_write_workflow_allowlist'])
        self.assertNotIn(WORKFLOW, self.policy['statuses_write_workflow_allowlist'])


if __name__ == '__main__':
    unittest.main()
