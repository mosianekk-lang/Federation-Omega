from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BubblesCareerCapabilityFoundryAdmissionTests(unittest.TestCase):
    def test_foundry_source_market_signals_and_suite_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "career_capability_foundry.py").is_file())
        self.assertTrue((ROOT / "bubbles" / "career_market_signals_20260812.json").is_file())
        self.assertTrue((ROOT / "tests" / "test_bubbles_career_capability_foundry.py").is_file())

    def test_focused_foundry_suite_executes(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_bubbles_career_capability_foundry", "-v"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
