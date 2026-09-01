from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarking/cfbe_omega/KIM_DATAVERSE_LEVEL7_PLUS_FEATURE_FREEZE_V1_20260901.md"


class KimDataverseLevel7PlusFeatureFreezeTests(unittest.TestCase):
    def test_failures_trigger_repair_not_feature_growth(self) -> None:
        text = FREEZE.read_text(encoding="utf-8")
        self.assertIn("Failures now trigger repair, not feature growth", text)


if __name__ == "__main__":
    unittest.main()
