from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

from proofos_omega.cli import (
    _DIAGNOSTIC_MAX_CHARS,
    _diagnostic_argv,
    _emit_failure_diagnostics,
    _redact_diagnostic,
)


class ProofOSFailureDiagnosticsTests(unittest.TestCase):
    def test_redaction_masks_common_secret_shapes_and_assignment_lines(self) -> None:
        synthetic_openai_key = "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz"
        raw = "\n".join(
            (
                "Authorization: Bearer abcdefghijklmnop",
                "token=abcdefghijklmnop",
                "password=hunter2",
                "api_key=abcdefghijklmnop",
                "github_pat_abcdefghijklmnopqrstuvwxyz",
                "ghp_abcdefghijklmnopqrstuvwxyz",
                synthetic_openai_key,
                "AIzaABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
                "AKIAABCDEFGHIJKLMNOP",
                "eyJabcdefghijk.abcdefghijkl.abcdefghijkl",
            )
        )
        redacted = _redact_diagnostic(raw)
        for secret in (
            "abcdefghijklmnop",
            "hunter2",
            "github_pat_abcdefghijklmnopqrstuvwxyz",
            "ghp_abcdefghijklmnopqrstuvwxyz",
            synthetic_openai_key,
            "AIzaABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
            "AKIAABCDEFGHIJKLMNOP",
            "eyJabcdefghijk.abcdefghijkl.abcdefghijkl",
        ):
            self.assertNotIn(secret, redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)

    def test_redaction_strips_ansi_and_preserves_traceback_tail_when_truncated(self) -> None:
        raw = "\x1b[31m" + ("x" * (_DIAGNOSTIC_MAX_CHARS + 100)) + "TRACEBACK_TAIL"
        redacted = _redact_diagnostic(raw)
        self.assertNotIn("\x1b[31m", redacted)
        self.assertTrue(redacted.startswith("[...diagnostic truncated"))
        self.assertTrue(redacted.endswith("TRACEBACK_TAIL"))
        self.assertLessEqual(
            len(redacted),
            _DIAGNOSTIC_MAX_CHARS + 100,
        )

    def test_diagnostic_argv_supports_only_registered_deterministic_kinds(self) -> None:
        glob = SimpleNamespace(kind="unittest_glob", target="test_phoenix*.py")
        module = SimpleNamespace(kind="unittest_module", target="tests.test_runtime")
        compileall = SimpleNamespace(kind="compileall", target="proofos_omega")
        unknown = SimpleNamespace(kind="shell", target="echo unsafe")
        self.assertEqual(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_phoenix*.py",
                "-v",
            ],
            _diagnostic_argv(glob),
        )
        self.assertEqual(
            [sys.executable, "-m", "unittest", "tests.test_runtime", "-v"],
            _diagnostic_argv(module),
        )
        self.assertEqual(
            [sys.executable, "-m", "compileall", "-q", "proofos_omega"],
            _diagnostic_argv(compileall),
        )
        self.assertIsNone(_diagnostic_argv(unknown))

    def test_failed_court_reruns_once_and_emits_bounded_redacted_diagnostic(self) -> None:
        spec = SimpleNamespace(
            kind="unittest_glob",
            target="test_phoenix*.py",
            timeout_seconds=30,
        )
        policy = SimpleNamespace(tests={"phoenix": spec})
        report = SimpleNamespace(
            results=(
                SimpleNamespace(
                    test_id="phoenix",
                    status="FAIL",
                    returncode=1,
                ),
            )
        )
        process = subprocess.CompletedProcess(
            args=["python"],
            returncode=1,
            stdout="AssertionError: secret=supersecret\n",
            stderr="Authorization: Bearer abcdefghijklmnop\n",
        )
        stream = io.StringIO()
        with patch("proofos_omega.cli.subprocess.run", return_value=process) as rerun:
            with redirect_stderr(stream):
                _emit_failure_diagnostics(policy=policy, report=report, repo_root=".")
        output = stream.getvalue()
        self.assertEqual(1, rerun.call_count)
        self.assertIn("PROOFOS_DIAGNOSTIC_BEGIN", output)
        self.assertIn("test_id=phoenix", output)
        self.assertIn("diagnostic_status=RERUN_COMPLETED", output)
        self.assertIn("PROOFOS_DIAGNOSTIC_END", output)
        self.assertNotIn("supersecret", output)
        self.assertNotIn("abcdefghijklmnop", output)
        self.assertIn("[REDACTED]", output)

    def test_pass_and_skip_results_never_trigger_diagnostic_rerun(self) -> None:
        spec = SimpleNamespace(
            kind="unittest_glob",
            target="test_phoenix*.py",
            timeout_seconds=30,
        )
        policy = SimpleNamespace(tests={"pass": spec, "skip": spec})
        report = SimpleNamespace(
            results=(
                SimpleNamespace(test_id="pass", status="PASS", returncode=0),
                SimpleNamespace(
                    test_id="skip",
                    status="SKIPPED_NOT_PRESENT",
                    returncode=0,
                ),
            )
        )
        stream = io.StringIO()
        with patch("proofos_omega.cli.subprocess.run") as rerun:
            with redirect_stderr(stream):
                _emit_failure_diagnostics(policy=policy, report=report, repo_root=".")
        rerun.assert_not_called()
        self.assertEqual("", stream.getvalue())

    def test_timeout_remains_diagnostic_only_and_redacts_partial_output(self) -> None:
        spec = SimpleNamespace(
            kind="unittest_module",
            target="tests.test_runtime",
            timeout_seconds=1,
        )
        policy = SimpleNamespace(tests={"runtime": spec})
        report = SimpleNamespace(
            results=(
                SimpleNamespace(
                    test_id="runtime",
                    status="FAIL_TIMEOUT",
                    returncode=124,
                ),
            )
        )
        timeout = subprocess.TimeoutExpired(
            cmd=["python"],
            timeout=1,
            output="password=hunter2\n",
            stderr="",
        )
        stream = io.StringIO()
        with patch("proofos_omega.cli.subprocess.run", side_effect=timeout):
            with redirect_stderr(stream):
                _emit_failure_diagnostics(policy=policy, report=report, repo_root=".")
        output = stream.getvalue()
        self.assertIn("diagnostic_status=RERUN_TIMEOUT", output)
        self.assertIn("[diagnostic rerun timed out]", output)
        self.assertNotIn("hunter2", output)
        self.assertIn("password=[REDACTED]", output)


if __name__ == "__main__":
    unittest.main()
