from __future__ import annotations

import subprocess
import sys
import unittest


class CFBEConvergenceClosureMatrixAirlockTests(unittest.TestCase):
    def test_focused_closure_matrix_suite_executes(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_cfbe_convergence_closure_matrix_v1",
                "-v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, combined)
        self.assertIn("Ran 6 tests", combined)
        self.assertIn("OK", combined)


if __name__ == "__main__":
    unittest.main()
