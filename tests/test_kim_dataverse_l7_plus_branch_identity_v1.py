from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_branch_identity_v1.json"


class KimDataverseLevel7PlusBranchIdentityTests(unittest.TestCase):
    def test_branch_identity_preserves_candidate_truth_boundary(self) -> None:
        data = json.loads(IDENTITY.read_text(encoding="utf-8"))
        self.assertEqual(1022, data["pr"])
        self.assertEqual(1019, data["programme_issue"])
        self.assertIn("candidate only", data["truth_boundary"])


if __name__ == "__main__":
    unittest.main()
