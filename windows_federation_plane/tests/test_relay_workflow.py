from __future__ import annotations

from pathlib import Path
import re
import unittest

import yaml


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "fuse-windows-relay-cloud-run-v1.yml"


class RelayWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.data = yaml.safe_load(cls.text)

    def test_owner_only_default_deny_dispatch(self):
        job = self.data["jobs"]["deploy-canary-promote"]
        self.assertIn("author_association == 'OWNER'", job["if"])
        self.assertIn("[FO-DISPATCH] FUSE_WINDOWS_RELAY_CLOUD_RUN_V1", job["if"])
        self.assertEqual(
            self.data["permissions"],
            {"contents": "read", "issues": "read", "id-token": "write"},
        )
        self.assertFalse(self.data["concurrency"]["cancel-in-progress"])

    def test_third_party_actions_are_sha_pinned(self):
        uses = re.findall(r"^\s*uses:\s*([^\s]+)", self.text, flags=re.MULTILINE)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40}$")
        self.assertIn("persist-credentials: false", self.text)

    def test_canary_precedes_promotion_and_has_rollback(self):
        self.assertIn("--no-traffic --tag relay-canary", self.text)
        self.assertIn("/healthz", self.text)
        self.assertIn("$CANARY_URL/mcp", self.text)
        self.assertIn("--to-revisions=\"$CANARY_REVISION=100\"", self.text)
        self.assertIn("if: failure() && env.PREVIOUS_REVISION != ''", self.text)
        self.assertLess(self.text.index("$CANARY_URL/healthz"), self.text.index("$CANARY_REVISION=100"))

    def test_secrets_are_provider_managed_and_receipt_is_redacted(self):
        self.assertIn("--set-secrets=\"FUSE_RELAY_ROOT_SECRET=$ROOT_SECRET:latest\"", self.text)
        self.assertIn('"secret_value_recorded": False', self.text)
        self.assertNotIn("echo $FUSE_RELAY_ROOT_SECRET", self.text)


if __name__ == "__main__":
    unittest.main()
