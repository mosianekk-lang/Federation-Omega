from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_ci_snapshot_v1.json"


class KimDataverseLevel7PlusCISnapshotTests(unittest.TestCase):
    def test_pre_admission_snapshot_does_not_self_authorize_merge_or_level7(self) -> None:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual("AWAITING_BLOCKING_COURTS", data["status"])
        self.assertFalse(data["merge_authorized_by_source"])
        self.assertFalse(data["operational_level7_claim"])


if __name__ == "__main__":
    unittest.main()
