"""Regression court for the FUSE One Apps Script zero-traffic bridge repair."""
from pathlib import Path
import re
import unittest

WORKFLOW = Path(".github/workflows/strategic-fuse-appsscript-read-zero-traffic.yml")

class StrategicFuseSecretlessCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def _deploy_block(self):
        marker = "- name: Deploy tagged zero-traffic candidate with explicit pre-authorized runtime identity"
        start = self.text.index(marker)
        tail = self.text[start:]
        nxt = tail.find("\n      - name:", len(marker))
        return tail if nxt < 0 else tail[:nxt]

    def test_candidate_clears_all_inherited_secrets(self):
        block = self._deploy_block()
        self.assertIn("--clear-secrets", block)
        self.assertNotIn("--remove-secrets", block)

    def test_candidate_keeps_zero_traffic_and_explicit_runtime_identity(self):
        block = self._deploy_block()
        self.assertIn("--no-traffic", block)
        self.assertIn('--service-account "$CANDIDATE_RUNTIME_SA"', block)

    def test_candidate_environment_is_rebuilt_as_closed_world(self):
        block = self._deploy_block()
        self.assertIn("--set-env-vars", block)
        self.assertIn("OPERATOR_AUDIENCE=", block)
        self.assertIn("OIDC_ALLOWED_PRINCIPALS=", block)

    def test_postdeploy_secretless_assertion_remains(self):
        self.assertIn("CANDIDATE_SECRET_BACKED_ENV_FORBIDDEN", self.text)
        self.assertIn("assert not secret_backed", self.text)

    def test_no_secret_accessor_grant_added_to_workflow(self):
        # Repair must remove the inherited dependency rather than widening IAM.
        lowered = self.text.lower()
        self.assertNotIn("roles/secretmanager.secretaccessor", lowered)
        self.assertNotIn("add-iam-policy-binding", lowered)

if __name__ == "__main__":
    unittest.main()
