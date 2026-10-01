from __future__ import annotations

import io
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout

from proofos_omega import core, cli


class FakeClock:
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now


def fixture(root, *, second=True, second_scope="GLOBAL", sleep=False):
    (root / "app").mkdir()
    (root / "app/x.py").write_text("VALUE = 1\n", encoding="utf-8")
    body = "import unittest\nclass T(unittest.TestCase):\n def test_ok(self):\n"
    body += "  import time; time.sleep(2)\n" if sleep else "  self.assertTrue(True)\n"
    for name in ("first", "second"):
        (root / f"court_{name}.py").write_text(body, encoding="utf-8")
    tests = [{"id": "first", "kind": "unittest_module", "target": "court_first", "always": True,
              "hard_always_run": True, "block_scope": "GLOBAL", "timeout_seconds": 30}]
    if second:
        tests.append({"id": "second", "kind": "unittest_module", "target": "court_second", "always": True,
                      "block_scope": second_scope, "timeout_seconds": 30})
    tests.append({"id": "full", "kind": "unittest_glob", "target": "test_*.py", "min_risk": "R5_RELEASE",
                  "sentinel_eligible": False, "block_scope": "GLOBAL", "timeout_seconds": 1200})
    policy = core.ProofPolicy({
        "schema": "FEDERATION-PROOFOS-OMEGA-V1", "version": "1.0.0", "authority_ceiling": "A1_INTERNAL",
        "external_effect_default": False, "selector": {"fallback_full_suite_test_id": "full", "sentinel_percent": 0},
        "subsystem_rules": [{"subsystem": "APP", "patterns": ["app/**"]}], "tests": tests,
    })
    manifest = core.ProofSelector(policy).compile_manifest(
        base_sha="1" * 40, head_sha="2" * 40, impact=core.ImpactCompiler(policy).assess(["app/x.py"])
    )
    return policy, manifest


class ProofOSExecutionBudgetTests(unittest.TestCase):
    def assert_descendant_stopped(self, child_pid):
        deadline = time.monotonic() + .5
        state_file = Path(f"/proc/{child_pid}/stat")
        # Some runners mount the host /proc into a child PID namespace. Use
        # signal-zero in our own namespace first; inspect zombie state only
        # when procfs uses that same namespace.
        matching_proc_namespace = os.readlink("/proc/self") == str(os.getpid())
        while True:
            try:
                os.kill(child_pid, 0)
                state = "LIVE"
            except ProcessLookupError:
                state = "GONE"
            if state == "LIVE" and matching_proc_namespace:
                try:
                    state = state_file.read_text().split()[2]
                except FileNotFoundError:
                    state = "GONE"
            if state in {"Z", "GONE"} or time.monotonic() >= deadline:
                break
            time.sleep(.01)
        self.assertIn(state, {"Z", "GONE"}, "owned descendant must no longer be running")

    def test_shared_budget_caps_repeatability_and_does_not_start_later_court(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root)
            clock = FakeClock()
            budget = core.ExecutionBudget(3, clock=clock)
            events, timeouts = [], []
            def execute(argv, **kwargs):
                timeouts.append(kwargs["timeout"])
                if len(timeouts) == 1:
                    self.assertEqual("COURT_START", events[-1]["event"])
                    clock.now = 2
                    return subprocess.CompletedProcess(argv, 1, b"", b"failure")
                clock.now = 3
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            with patch("proofos_omega.core.run_court_process", side_effect=execute):
                report = core.ProofRunner(policy=policy, repo_root=root).run(manifest, budget=budget, progress=events.append)
            self.assertEqual([3, 1], timeouts)
            self.assertEqual("FAIL", report.status)
            self.assertEqual("FAIL_BUDGET_EXHAUSTED", report.results[1].status)
            self.assertEqual(124, report.results[0].diagnostic_returncode)
            self.assertIn("BUDGET_EXHAUSTED", {row["event"] for row in events})
            self.assertEqual("RUN_COMPLETE", events[-1]["event"])
            self.assertEqual(2, len(report.results))

    def test_unrun_shadow_court_never_produces_green_admission(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second_scope="SHADOW")
            clock = FakeClock()
            budget = core.ExecutionBudget(1, clock=clock)
            def execute(argv, **kwargs):
                clock.now = 1
                return subprocess.CompletedProcess(argv, 0, b"ok", b"")
            with patch("proofos_omega.core.run_court_process", side_effect=execute) as process:
                report = core.ProofRunner(policy=policy, repo_root=root).run(manifest, budget=budget)
            self.assertEqual(1, process.call_count)
            self.assertEqual("FAIL", report.status)
            self.assertIn("second:PROOF_BUDGET_EXHAUSTED", report.blocking_failures)
            self.assertEqual(manifest.manifest_sha256, report.manifest_sha256)

    def test_failure_output_is_reused_redacted_without_a_third_execution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second=False)
            runner = core.ProofRunner(policy=policy, repo_root=root)
            budget = core.ExecutionBudget(3, clock=FakeClock())
            failures = [subprocess.CompletedProcess([], 1, b"password=hunter2\n", b"AssertionError"),
                        subprocess.CompletedProcess([], 0, b"passed on retry", b"")]
            stream = io.StringIO()
            with patch("proofos_omega.core.run_court_process", side_effect=failures) as process:
                report = runner.run(manifest, budget=budget)
                with redirect_stderr(stream):
                    cli._emit_failure_diagnostics(policy=policy, report=report, repo_root=root,
                                                  budget=budget, captured_output=runner.failure_outputs)
            self.assertEqual(2, process.call_count)
            self.assertEqual("FAIL", report.status)
            self.assertEqual("NONDETERMINISTIC_RERUN_PASS", report.results[0].repeatability)
            self.assertIn("CAPTURED_COURT_OUTPUT", stream.getvalue())
            self.assertNotIn("hunter2", stream.getvalue())

    def test_existing_repeatability_probe_is_not_repeated_by_cli(self):
        result = SimpleNamespace(test_id="first", status="FAIL", returncode=1, diagnostic_returncode=1,
                                 repeatability="REPRODUCIBLE_FAIL")
        policy = SimpleNamespace(tests={"first": SimpleNamespace(kind="unittest_module", target="court_first", timeout_seconds=30)})
        with patch("proofos_omega.cli.subprocess.run") as process, redirect_stderr(io.StringIO()):
            cli._emit_failure_diagnostics(policy=policy, report=SimpleNamespace(results=[result]), repo_root=".")
        self.assertEqual(0, process.call_count)

    def test_cli_diagnostic_consumes_only_remaining_shared_budget(self):
        clock = FakeClock()
        budget = core.ExecutionBudget(5, clock=clock)
        clock.now = 4
        result = SimpleNamespace(test_id="first", status="FAIL", returncode=1)
        policy = SimpleNamespace(tests={"first": SimpleNamespace(kind="unittest_module", target="court_first", timeout_seconds=30)})
        with patch("proofos_omega.cli.run_court_process", return_value=subprocess.CompletedProcess([], 1, "", "")) as process, redirect_stderr(io.StringIO()):
            cli._emit_failure_diagnostics(policy=policy, report=SimpleNamespace(results=[result]), repo_root=".", budget=budget)
        self.assertEqual(1, process.call_args.kwargs["timeout"])
        clock.now = 5
        with patch("proofos_omega.cli.run_court_process") as process, redirect_stderr(io.StringIO()):
            cli._emit_failure_diagnostics(policy=policy, report=SimpleNamespace(results=[result]), repo_root=".", budget=budget)
        self.assertEqual(0, process.call_count)

    def test_real_short_subprocess_timeout_preserves_failed_report_and_progress(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second=False, sleep=True)
            events = []
            started = time.monotonic()
            runner = core.ProofRunner(policy=policy, repo_root=root)
            report = runner.run(manifest, budget=core.ExecutionBudget(.08), progress=events.append)
            self.assertLess(time.monotonic() - started, 1.5)
            self.assertEqual("FAIL", report.status)
            self.assertEqual("FAIL_BUDGET_EXHAUSTED", report.results[0].status)
            self.assertEqual(124, report.results[0].returncode)
            self.assertIn("BUDGET_EXHAUSTED", {row["event"] for row in events})

    def test_budget_does_not_change_proof_key_or_bypass_hard_always_floor(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second=False)
            cache = core.ProofCache(root / "cache")
            runner = core.ProofRunner(policy=policy, repo_root=root, cache=cache)
            with patch("proofos_omega.core.run_court_process", return_value=subprocess.CompletedProcess([], 0, b"ok", b"")) as process:
                first = runner.run(manifest)
                second = runner.run(manifest, budget=core.ExecutionBudget(5, clock=FakeClock()))
            self.assertEqual(2, process.call_count)
            self.assertFalse(second.results[0].reused_from_cache)
            self.assertEqual(first.results[0].proof_key, second.results[0].proof_key)

    def test_cli_flag_and_progress_checkpoint_exist_before_child_starts(self):
        args = cli.build_parser().parse_args(["run", "--policy", "p", "--manifest", "m", "--output", "o", "--budget-seconds", "3"])
        self.assertEqual(3, args.budget_seconds)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second=False)
            args = SimpleNamespace(policy="p", manifest="m", repo_root=str(root), output=str(root / "report.json"),
                                   cache_dir=None, budget_seconds=3, progress_output=None)
            def execute(argv, **kwargs):
                snapshot = json.loads((root / "report.progress.json").read_text())
                self.assertEqual("COURT_START", snapshot["event"])
                self.assertEqual(manifest.manifest_sha256, snapshot["manifest_sha256"])
                self.assertEqual("IN_PROGRESS", snapshot["status"])
                return subprocess.CompletedProcess(argv, 0, b"ok", b"")
            with patch.object(cli.ProofPolicy, "from_path", return_value=policy), patch.object(cli, "load_manifest", return_value=manifest), patch("proofos_omega.core.run_court_process", side_effect=execute), redirect_stdout(io.StringIO()):
                self.assertEqual(0, cli.run_command(args))
            final = json.loads((root / "report.json").read_text())
            self.assertEqual("PASS", final["status"])
            self.assertEqual("RUN_COMPLETE", json.loads((root / "report.progress.json").read_text())["event"])

    def test_cli_refuses_progress_path_alias_before_starting_a_court(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second=False)
            report_path = str(root / "report.json")
            args = SimpleNamespace(policy="p", manifest="m", repo_root=str(root), output=report_path,
                                   cache_dir=None, budget_seconds=3, progress_output=report_path)
            with patch.object(cli.ProofPolicy, "from_path", return_value=policy), patch.object(cli, "load_manifest", return_value=manifest), patch("proofos_omega.core.run_court_process") as process:
                with self.assertRaisesRegex(ValueError, "progress output must differ"):
                    cli.run_command(args)
            self.assertEqual(0, process.call_count)

    def test_invalid_budget_is_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises((ValueError, core.RunnerError)):
                core.ExecutionBudget(value)

    def test_long_secret_prefix_is_redacted_before_output_is_cropped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second=False)
            runner = core.ProofRunner(policy=policy, repo_root=root)
            synthetic = "q" * 30000
            failure = subprocess.CompletedProcess([], 1, ("password=" + synthetic + "\n").encode(), b"AssertionError")
            stream = io.StringIO()
            with patch("proofos_omega.core.run_court_process", return_value=failure):
                report = runner.run(manifest)
            with redirect_stderr(stream):
                cli._emit_failure_diagnostics(policy=policy, report=report, repo_root=root, captured_output=runner.failure_outputs)
            self.assertNotIn("q" * 100, stream.getvalue())
            self.assertIn("password=[REDACTED]", stream.getvalue())

    @unittest.skipUnless(os.name == "posix" and Path("/proc").exists(), "Linux owned process group test")
    def test_budget_timeout_kills_inherited_descendant_and_retained_pipes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            policy, manifest = fixture(root, second=False)
            (root / "court_first.py").write_text(
                "import subprocess, sys, time\nfrom pathlib import Path\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                "Path('descendant.pid').write_text(str(child.pid))\n"
                "time.sleep(30)\n", encoding="utf-8"
            )
            started = time.monotonic()
            report = core.ProofRunner(policy=policy, repo_root=root).run(manifest, budget=core.ExecutionBudget(.3))
            self.assertLess(time.monotonic() - started, 2)
            self.assertEqual("FAIL_BUDGET_EXHAUSTED", report.results[0].status)
            child_pid = int((root / "descendant.pid").read_text())
            self.assert_descendant_stopped(child_pid)

    @unittest.skipUnless(os.name == "posix" and Path("/proc").exists(), "Linux owned process group test")
    def test_failed_wrapper_exit_also_cleans_descendant_held_pipes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = (
                "import subprocess, sys, os\nfrom pathlib import Path\n"
                "assert os.environ.get('PROOFOS_PARENT_OWNS_PROCESS_GROUP') == '1'\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                "Path('descendant.pid').write_text(str(child.pid))\n"
                "sys.exit(2)\n"
            )
            started = time.monotonic()
            result = core.run_court_process([sys.executable, "-c", script], budgeted=True, cwd=root,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1, check=False)
            self.assertEqual(2, result.returncode)
            self.assertLess(time.monotonic() - started, 1)
            self.assert_descendant_stopped(int((root / "descendant.pid").read_text()))

    @unittest.skipUnless(os.name == "posix" and Path("/proc").exists(), "POSIX graceful child cleanup test")
    def test_timeout_grace_allows_owner_to_close_its_detached_child(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = (
                "import subprocess, sys, signal, time\nfrom pathlib import Path\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)'], start_new_session=True)\n"
                "def close_child(signum, frame):\n"
                " child.terminate(); child.wait(timeout=1)\n"
                " Path('cleanup.done').write_text('closed')\n"
                " sys.exit(0)\n"
                "signal.signal(signal.SIGTERM, close_child)\n"
                "Path('descendant.pid').write_text(str(child.pid))\n"
                "time.sleep(5)\n"
            )
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    core.run_court_process([sys.executable, "-c", script], budgeted=True, cwd=root,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=.3, check=False)
                self.assertTrue((root / "cleanup.done").exists(), "owned parent must receive bounded TERM cleanup opportunity")
                self.assert_descendant_stopped(int((root / "descendant.pid").read_text()))
            finally:
                if (root / "descendant.pid").exists():
                    # Test-created detached child only; no process discovery or
                    # broad cleanup. This also contains a failed regression.
                    try:
                        os.kill(int((root / "descendant.pid").read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    @unittest.skipUnless(os.name == "posix" and Path("/proc").exists(), "POSIX bounded TERM fallback test")
    def test_term_resistant_owned_process_is_killed_after_finite_grace(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = (
                "import signal,time,os\nfrom pathlib import Path\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "Path('owned.pid').write_text(str(os.getpid()))\n"
                "time.sleep(5)\n"
            )
            started = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                core.run_court_process([sys.executable, "-c", script], budgeted=True, cwd=root,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=.3, check=False)
            self.assertLess(time.monotonic() - started, 1.5)
            self.assert_descendant_stopped(int((root / "owned.pid").read_text()))


if __name__ == "__main__":
    unittest.main()
