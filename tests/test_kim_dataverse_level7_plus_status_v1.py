from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "benchmarking/cfbe_omega/kim_dataverse_level7_plus_status_v1.json"


class KimDataverseLevel7PlusStatusTests(unittest.TestCase):
    def test_status_truthfully_caps_operational_maturity(self) -> None:
        data = json.loads(STATUS.read_text(encoding="utf-8"))
        self.assertEqual("UNPROVEN", data["level7_operational"])
        self.assertEqual("UNPROVEN", data["level8_operational"])
        self.assertEqual("RESEARCH_ONLY", data["level9_plus"])
        self.assertEqual("REPAIR_CURRENT_SERVING_PHOENIX_AND_ADMIT_EXACT_HEAD", data["next_automatic_lane"])


if __name__ == "__main__":
    unittest.main()
