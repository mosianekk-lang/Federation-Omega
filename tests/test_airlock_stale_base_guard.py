from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "github-airlock.yml"
IDENTITY_TOOL = ROOT / "tools" / "airlock_execution_identity.py"


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
        self.assertIn("HEAD_ANCESTRY_VERIFIED", self.text)

    def test_checkout_is_exact_admitted_head_with_full_history_and_no_credentials(self) -> None:
        self.assertIn(
            "ref: ${{ github.event.pull_request.head.sha || "
            "github.event.merge_group.head_sha || github.sha }}",
            self.text,
        )
        self.assertIn("fetch-depth: 0", self.text)
        self.assertIn("persist-credentials: false", self.text)

    def test_execution_identity_is_bound_before_setup_and_regressions(self) -> None:
        resolve = self.text.index(
            "name: Resolve admission comparison and provider provenance"
        )
        ancestry = self.text.index("name: Enforce pull-request head ancestry")
        identity = self.text.index("name: Bind execution identity to admitted head")
        setup_python = self.text.index("actions/setup-python@")
        first_tests = self.text.index("name: Run Airlock regression tests")
        self.assertLess(resolve, ancestry)
        self.assertLess(ancestry, identity)
        self.assertLess(identity, setup_python)
        self.assertLess(identity, first_tests)
        self.assertIn("tools/airlock_execution_identity.py bind", self.text)
        self.assertIn("EVENT_SHA: ${{ steps.refs.outputs.event_sha }}", self.text)
        self.assertIn("--exporter phoenix/build_exports.py", self.text)

    def test_phoenix_suite_marks_only_successful_bound_exporter_execution(self) -> None:
        phoenix = self.text.index("name: Run Phoenix export purity regression tests")
        mark = self.text.index("mark-phoenix-verified")
        final_verify = self.text.index("name: Verify final execution identity receipt")
        admission = self.text.index("name: Enforce default-deny admission policy")
        self.assertLess(phoenix, mark)
        self.assertLess(mark, final_verify)
        self.assertLess(final_verify, admission)
        self.assertIn("--test-suite tests/test_phoenix_exports.py", self.text)

    def test_execution_identity_receipt_is_published_and_uploaded(self) -> None:
        self.assertIn("airlock-output/execution-identity-report.json", self.text)
        self.assertIn("## Airlock Execution Identity", self.text)
        self.assertIn(
            "if: always() && hashFiles('airlock-output/*.json') != ''",
            self.text,
        )

    def test_identity_tool_binds_marks_and_verifies_exact_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "airlock@example.invalid"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Airlock Test"],
                cwd=root,
                check=True,
            )
            workflow = root / ".github" / "workflows" / "github-airlock.yml"
            exporter = root / "phoenix" / "build_exports.py"
            workflow.parent.mkdir(parents=True)
            exporter.parent.mkdir(parents=True)
            workflow.write_text("name: test\n", encoding="utf-8")
            exporter.write_text("print('export')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            report = root / "airlock-output" / "execution-identity-report.json"
            event_sha = "f" * 40
            bind = subprocess.run(
                [
                    sys.executable,
                    str(IDENTITY_TOOL),
                    "bind",
                    "--repo-root",
                    str(root),
                    "--repository",
                    "example/repository",
                    "--event",
                    "pull_request",
                    "--base",
                    head,
                    "--head",
                    head,
                    "--event-sha",
                    event_sha,
                    "--workflow",
                    ".github/workflows/github-airlock.yml",
                    "--exporter",
                    "phoenix/build_exports.py",
                    "--run-id",
                    "1",
                    "--run-attempt",
                    "1",
                    "--report",
                    str(report),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, bind.returncode, bind.stdout + bind.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("IDENTITY_BOUND", payload["status"])
            self.assertEqual(head, payload["checkout"]["sha"])
            self.assertEqual(
                "GITHUB_GENERATED_MERGE_REF_OBSERVATION_ONLY",
                payload["event_sha_role"],
            )
            self.assertEqual(
                hashlib.sha256(exporter.read_bytes()).hexdigest(),
                payload["phoenix_exporter"]["sha256"],
            )

            mark = subprocess.run(
                [
                    sys.executable,
                    str(IDENTITY_TOOL),
                    "mark-phoenix-verified",
                    "--report",
                    str(report),
                    "--test-suite",
                    "tests/test_phoenix_exports.py",
                    "--test-command",
                    "python -m unittest discover -s tests -p test_phoenix_exports.py -v",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, mark.returncode, mark.stdout + mark.stderr)
            verify = subprocess.run(
                [
                    sys.executable,
                    str(IDENTITY_TOOL),
                    "verify",
                    "--report",
                    str(report),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, verify.returncode, verify.stdout + verify.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("VERIFIED", payload["status"])
            self.assertEqual(
                "DEDICATED_TEST_SUITE_PASSED",
                payload["phoenix_exporter"]["execution_status"],
            )

    def test_identity_tool_fails_closed_on_checkout_head_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "airlock@example.invalid"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Airlock Test"],
                cwd=root,
                check=True,
            )
            workflow = root / ".github" / "workflows" / "github-airlock.yml"
            exporter = root / "phoenix" / "build_exports.py"
            workflow.parent.mkdir(parents=True)
            exporter.parent.mkdir(parents=True)
            workflow.write_text("name: test\n", encoding="utf-8")
            exporter.write_text("print('export')\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            report = root / "report.json"
            mismatch = "0" * 40
            process = subprocess.run(
                [
                    sys.executable,
                    str(IDENTITY_TOOL),
                    "bind",
                    "--repo-root",
                    str(root),
                    "--repository",
                    "example/repository",
                    "--event",
                    "pull_request",
                    "--base",
                    head,
                    "--head",
                    mismatch,
                    "--event-sha",
                    head,
                    "--workflow",
                    ".github/workflows/github-airlock.yml",
                    "--exporter",
                    "phoenix/build_exports.py",
                    "--run-id",
                    "1",
                    "--run-attempt",
                    "1",
                    "--report",
                    str(report),
                ],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(0, process.returncode)
            self.assertIn("EXECUTION_HEAD_MISMATCH", process.stdout)
            self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
