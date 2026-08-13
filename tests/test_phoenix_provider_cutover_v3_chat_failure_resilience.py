from __future__ import annotations

import subprocess
import sys
import unittest


class ChatFailureResilienceAirlockTests(unittest.TestCase):
    def test_focused_chat_failure_resilience_suite_executes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "evidenceops/build_system/tests",
                "-p",
                "test_chat_failure_resilience.py",
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
