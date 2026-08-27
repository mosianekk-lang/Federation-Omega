from __future__ import annotations

import io
import subprocess
import sys
import unittest


class CFRECommandBusAdmissionTests(unittest.TestCase):
    def test_bubbles_command_bus_cfre_suite_executes(self):
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_bubbles_command_bus", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, combined)
        self.assertIn("Ran ", combined)
        self.assertIn("OK", combined)
        self.assertIn(
            "test_archon_apps_script_public_probe_runs_as_read_only_command",
            combined,
        )
        self.assertIn(
            "test_archon_apps_script_public_probe_cannot_be_promoted_to_write",
            combined,
        )

    def test_omega_autofix_failure_win_v2_canary_executes(self) -> None:
        suite = unittest.defaultTestLoader.loadTestsFromName(
            "tests.test_autofix_failure_win_v2"
        )
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        evidence = stream.getvalue()
        self.assertTrue(result.wasSuccessful(), evidence)
        self.assertEqual(1, result.testsRun, evidence)
        self.assertIn("test_cfre_native_recovery_then_v2_canary", evidence)


if __name__ == "__main__":
    unittest.main()
