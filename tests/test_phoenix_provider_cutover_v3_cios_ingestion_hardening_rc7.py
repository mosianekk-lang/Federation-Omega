from __future__ import annotations

import subprocess
import sys
import unittest


class CIOSIngestionHardeningRC7AirlockTests(unittest.TestCase):
    def test_focused_ooxml_hardening_suite_executes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "evidenceops/capital_intelligence_os/tests",
                "-p",
                "test_ingestion_hardening_rc7.py",
                "-v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("Ran 12 tests", combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
