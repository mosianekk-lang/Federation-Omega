from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_admission_lock_v1.json"


class KimDataverseLevel7PlusAdmissionLockTests(unittest.TestCase):
    def test_admission_lock_allows_repairs_not_feature_growth(self) -> None:
        data = json.loads(LOCK.read_text(encoding="utf-8"))
        self.assertFalse(data["feature_growth"])
        self.assertIn("DEFECT_REPAIR", data["allowed_changes_until_admission"])
        self.assertFalse(data["operational_level7_claim"])


if __name__ == "__main__":
    unittest.main()
