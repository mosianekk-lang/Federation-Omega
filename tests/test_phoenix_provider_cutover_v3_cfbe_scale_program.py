from __future__ import annotations

import subprocess
import sys
import unittest


class CFBEFederationScaleAirlockTests(unittest.TestCase):
    def test_focused_scale_program_suite_executes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_cfbe_omega_federation_scale_program",
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
