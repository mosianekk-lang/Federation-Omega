from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "github-airlock.yml"


class AirlockStaleBaseGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_pull_request_and_merge_group_are_guarded(self) -> None:
        self.assertIn("name: Enforce pull-request head ancestry", self.text)
        self.assertIn(
            "github.event_name == 'pull_request' || github.event_name == 'merge_group'",
            self.text,
        )

    def test_guard_uses_resolved_base_and_head(self) -> None:
        self.assertIn("BASE_SHA: ${{ steps.refs.outputs.base }}", self.text)
        self.assertIn("HEAD_SHA: ${{ steps.refs.outputs.head }}", self.text)
        self.assertIn(
            'git merge-base --is-ancestor "$BASE_SHA" "$HEAD_SHA"',
            self.text,
        )

    def test_stale_head_fails_closed(self) -> None:
        self.assertIn("STALE_BASE_HEAD_REJECTED", self.text)
        self.assertIn("exit 1", self.text)
        self.assertIn("HEAD_ANCESTRY_VERIFIED", self.text)

    def test_checkout_has_full_history_without_credentials(self) -> None:
        self.assertIn("fetch-depth: 0", self.text)
        self.assertIn("persist-credentials: false", self.text)


if __name__ == "__main__":
    unittest.main()
