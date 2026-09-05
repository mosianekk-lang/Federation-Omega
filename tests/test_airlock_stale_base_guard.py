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
            '"/repos/${GITHUB_REPOSITORY}/compare/${BASE_SHA}...${HEAD_SHA}"',
            self.text,
        )
        self.assertIn("--jq '.merge_base_commit.sha'", self.text)
        self.assertIn('if [[ "$merge_base" != "$BASE_SHA" ]]', self.text)

    def test_stale_head_fails_closed(self) -> None:
        self.assertIn("STALE_BASE_HEAD_REJECTED", self.text)
        self.assertIn("HEAD_ANCESTRY_VERIFIED", self.text)

    def test_exact_comparison_objects_are_fetched_before_ancestry(self) -> None:
        fetch_objects = self.text.index("name: Fetch exact comparison objects")
        ancestry = self.text.index("name: Enforce pull-request head ancestry")
        self.assertIn(
            'git fetch --no-tags --depth=1 origin "$BASE_SHA" "$HEAD_SHA"',
            self.text,
        )
        self.assertIn('git cat-file -e "${HEAD_SHA}^{commit}"', self.text)
        self.assertLess(fetch_objects, ancestry)

    def test_ancestry_runs_before_setup_and_regression_suites(self) -> None:
        resolve = self.text.index(
            "name: Resolve admission comparison and provider provenance"
        )
        fetch_objects = self.text.index("name: Fetch exact comparison objects")
        ancestry = self.text.index("name: Enforce pull-request head ancestry")
        setup_python = self.text.index("actions/setup-python@")
        first_tests = self.text.index("name: Run Airlock regression tests")
        self.assertLess(resolve, fetch_objects)
        self.assertLess(fetch_objects, ancestry)
        self.assertLess(ancestry, setup_python)
        self.assertLess(ancestry, first_tests)

    def test_declared_dependencies_are_installed_before_regression_suites(self) -> None:
        setup_python = self.text.index("actions/setup-python@")
        install = self.text.index("name: Install declared test dependencies")
        first_tests = self.text.index("name: Run Airlock regression tests")
        self.assertIn(
            "python -m pip install --disable-pip-version-check --no-input "
            "-r requirements.txt",
            self.text,
        )
        self.assertLess(setup_python, install)
        self.assertLess(install, first_tests)

    def test_checkout_is_bounded_without_credentials(self) -> None:
        self.assertIn("fetch-depth: 2", self.text)
        self.assertNotIn("fetch-depth: 0", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_early_failure_does_not_create_secondary_artifact_failure(self) -> None:
        self.assertIn(
            "if: always() && hashFiles('airlock-output/*.json') != ''",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
