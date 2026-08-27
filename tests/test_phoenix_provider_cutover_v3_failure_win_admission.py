from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FailureWinProofConvertibilityAdmissionTests(unittest.TestCase):
    """Bind Failure-Win convertibility regressions to the existing Airlock.

    This reuses the already-approved provider-cutover-v3 wildcard instead of
    creating or broadening workflow authority.
    """

    def test_failure_win_convertibility_suite_executes(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_failure_win_proof_convertibility.py",
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "Failure-Win proof-convertibility regression suite failed.\n"
                f"stdout:\n{proc.stdout[-6000:]}\n"
                f"stderr:\n{proc.stderr[-6000:]}"
            )

    def test_convertibility_source_and_regression_are_present(self):
        required = (
            ROOT / "ao_harmonic_v3" / "failure_win_proof_convertibility.py",
            ROOT / "tests" / "test_failure_win_proof_convertibility.py",
        )
        self.assertTrue(all(path.is_file() for path in required))


if __name__ == "__main__":
    unittest.main()
