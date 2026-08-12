from __future__ import annotations

import subprocess
import sys
import unittest


class CIOSFinishRC5AirlockTests(unittest.TestCase):
    def test_focused_internal_completion_suite_executes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "evidenceops/capital_intelligence_os/tests",
                "-p",
                "test_finish_rc5.py",
                "-v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("Ran 13 tests", combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
