from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HEAD = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_admission_head_v1.json"


class KimDataverseLevel7PlusAdmissionHeadTests(unittest.TestCase):
    def test_admission_head_is_frozen_and_awaiting_ci(self) -> None:
        data = json.loads(HEAD.read_text(encoding="utf-8"))
        self.assertEqual(1022, data["pr"])
        self.assertEqual("FEATURE_FROZEN_AWAITING_CI", data["state"])


if __name__ == "__main__":
    unittest.main()
