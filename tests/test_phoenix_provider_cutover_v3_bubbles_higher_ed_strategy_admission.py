from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BubblesHigherEdStrategyAdmissionTests(unittest.TestCase):
    def test_capability_map_lab_and_suite_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "higher_ed_leadership_capability_map_20260812.json").is_file())
        self.assertTrue((ROOT / "bubbles" / "higher_ed_digital_strategy_lab.py").is_file())
        self.assertTrue((ROOT / "tests" / "test_bubbles_higher_ed_digital_strategy_lab.py").is_file())

    def test_focused_higher_ed_strategy_suite_executes(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_bubbles_higher_ed_digital_strategy_lab", "-v"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
