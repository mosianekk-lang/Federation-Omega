from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BubblesEdTechLearningAnalyticsAdmissionTests(unittest.TestCase):
    def test_source_note_and_suite_are_present(self) -> None:
        self.assertTrue((ROOT / "bubbles" / "edtech_learning_analytics_lab.py").is_file())
        self.assertTrue((ROOT / "bubbles" / "EDTECH_LEARNING_ANALYTICS_CAPABILITY_NOTE.md").is_file())
        self.assertTrue((ROOT / "tests" / "test_bubbles_edtech_learning_analytics_lab.py").is_file())

    def test_focused_suite_executes(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_bubbles_edtech_learning_analytics_lab", "-v"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
