from __future__ import annotations

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "fuse-windows-relay-cloud-run-v1.yml"


class RelayWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_owner_only_default_deny_dispatch(self):
        self.assertIn("author_association == 'OWNER'", self.text)
        self.assertIn("[FO-DISPATCH] FUSE_WINDOWS_RELAY_CLOUD_RUN_V1", self.text)
        self.assertRegex(
            self.text,
            r"permissions:\n  contents: read\n  issues: read\n  id-token: write",
        )
        self.assertIn("cancel-in-progress: false", self.text)

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
