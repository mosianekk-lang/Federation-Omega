from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BubblesOmega2AdmissionTests(unittest.TestCase):
    def test_omega2_source_and_portable_kernel_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "adaptive_organisation.py").is_file())
        self.assertTrue((ROOT / "bubbles" / "BUBBLES_OMEGA2_PORTABLE_KERNEL.md").is_file())

    def test_omega2_focused_suite_executes(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_bubbles_omega2", "-v"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
