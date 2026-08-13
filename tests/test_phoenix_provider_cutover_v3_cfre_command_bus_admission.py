from __future__ import annotations

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
        self.assertIn("Ran 10 tests", combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
