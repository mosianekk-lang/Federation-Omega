from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CFBEAdmissionTests(unittest.TestCase):
    """Bind CFBE focused regressions to the already-approved Airlock wildcard.

    This deliberately reuses the existing Federation Omega Airlock execution
    surface instead of adding a new workflow or widening workflow authority.
    """

    def test_cfbe_focused_suite_executes(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_cfbe*.py",
                "-v",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            self.fail(
                "CFBE focused regression suite failed.\n"
                f"stdout:\n{proc.stdout[-6000:]}\n"
                f"stderr:\n{proc.stderr[-6000:]}"
            )

    def test_resource_gate_and_estate_analyzer_are_present(self):
        required = (
            ROOT / "benchmarking" / "cfbe_omega" / "resource_gate.py",
            ROOT / "benchmarking" / "cfbe_omega" / "estate_audit.py",
            ROOT / "tests" / "test_cfbe_omega.py",
            ROOT / "tests" / "test_cfbe_resource_estate.py",
        )
        self.assertTrue(all(path.is_file() for path in required))


if __name__ == "__main__":
    unittest.main()
