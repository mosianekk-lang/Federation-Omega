from __future__ import annotations

import subprocess
import sys
import unittest


class CIOSQualificationDemoAirlockTests(unittest.TestCase):
    def test_focused_qualification_and_demo_suite_executes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "evidenceops/capital_intelligence_os/tests",
                "-p",
                "test_qualification_demo_v1.py",
                "-v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("Ran 5 tests", combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
