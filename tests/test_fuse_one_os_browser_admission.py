"""Execute the real isolated browser/runtime court; missing tooling is a failure."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def start_court_process(argv, env):
    # Node and the fixture inherit the outer group in budgeted admission.
    # Playwright starts Chromium separately; bounded TERM grace lets its owner
    # close that browser. A nested wrapper session would bypass outer cleanup.
    owns_group = os.name != "nt" and env.get("PROOFOS_PARENT_OWNS_PROCESS_GROUP") != "1"
    return subprocess.Popen(
        argv, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, start_new_session=owns_group,
    ), owns_group


class FuseOneBrowserAdmissionTests(unittest.TestCase):
    def test_budgeted_browser_descendants_inherit_runner_group(self):
        env = {**os.environ, "PROOFOS_PARENT_OWNS_PROCESS_GROUP": "1"}
        process, owns_group = start_court_process(
            [sys.executable, "-c", "import os; print(getattr(os, 'getpgrp', lambda: None)())"], env,
        )
        output, _ = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0)
        self.assertFalse(owns_group)
        self.assertEqual(output.strip(), str(getattr(os, "getpgrp", lambda: None)()))

    def test_standalone_browser_keeps_its_own_cleanup_group(self):
        env = dict(os.environ)
        env.pop("PROOFOS_PARENT_OWNS_PROCESS_GROUP", None)
        process, owns_group = start_court_process(
            [sys.executable, "-c", "import os; print(getattr(os, 'getpgrp', lambda: None)())"], env,
        )
        output, _ = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(owns_group, os.name != "nt")
        self.assertEqual(output.strip(), str(process.pid if owns_group else None))

    def test_browser_runtime_contracts_are_executed(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for browser admission")
        with tempfile.TemporaryDirectory(prefix="fuse-one-browser-admission-") as temporary:
            env = {
                **os.environ,
                "FUSE_BROWSER_TEST_PYTHON": sys.executable,
                "FUSE_BROWSER_TEST_OUTPUT": temporary,
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            process, owns_group = start_court_process([node, "scripts/fuse_one_os_browser_test.mjs"], env)
            try:
                output, _ = process.communicate(timeout=150)
            except subprocess.TimeoutExpired:
                if owns_group:
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.kill()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    if owns_group:
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.communicate(timeout=5)
                self.fail("Browser admission exceeded its bounded execution time")
            self.assertEqual(process.returncode, 0, output[-6000:])
            receipt_path = Path(temporary) / "ui_browser_result.json"
            self.assertTrue(receipt_path.is_file(), "A successful process must supply its browser receipt")
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["schema"], "FUSE_ONE_UI_BROWSER_CHECKS_V1")
            self.assertGreaterEqual(receipt["test_count"], 11)
            self.assertEqual(receipt["test_count"], len(receipt["checks"]))
            self.assertEqual(receipt["test_count"], len({check["name"] for check in receipt["checks"]}))
            self.assertTrue(all(check["passed"] is True for check in receipt["checks"]))
            self.assertIs(receipt["provider_called"], False)
            self.assertIs(receipt["deployed"], False)
            self.assertIs(receipt["production_certified"], False)


if __name__ == "__main__":
    unittest.main()
