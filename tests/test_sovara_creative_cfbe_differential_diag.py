from __future__ import annotations

import subprocess
import sys
import unittest


class CFBEDifferentialDiagnosticTests(unittest.TestCase):
    def test_exact_cfbe_induced_v3_failures_are_visible(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_phoenix_provider_cutover_v3*.py",
                "-v",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            stderr = result.stderr
            markers = [
                marker
                for marker in ("FAIL:", "ERROR:", "Traceback (most recent call last):", "FAILED (")
                if marker in stderr
            ]
            self.fail(
                "CFBE_V3_DIAGNOSTIC\n"
                f"RETURN_CODE={result.returncode}\n"
                f"MARKERS={markers}\n"
                "STDERR_TAIL:\n"
                + stderr[-12000:]
            )


if __name__ == "__main__":
    unittest.main()
