from __future__ import annotations

import subprocess
import sys
import unittest


class CFBEDifferentialDiagnosticTests(unittest.TestCase):
    def test_exact_cfbe_induced_phoenix_failures_are_visible(self):
        failures: list[str] = []
        for pattern in ("test_phoenix_exports.py", "test_phoenix_provider_cutover_v3*.py"):
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    pattern,
                    "-v",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                failures.append(
                    f"PATTERN={pattern}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
                )
        if failures:
            self.fail("\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
