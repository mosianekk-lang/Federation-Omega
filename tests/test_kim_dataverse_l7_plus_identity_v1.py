from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_identity_v1.json"


class KimDataverseLevel7PlusIdentityTests(unittest.TestCase):
    def test_identity_distinguishes_source_candidate_from_operational_level7(self) -> None:
        data = json.loads(IDENTITY.read_text(encoding="utf-8"))
        self.assertEqual("LEVEL6_SOURCE_CANDIDATE", data["current_source_claim"])
        self.assertEqual("LEVEL7_NOT_YET_EMPIRICALLY_PROVEN", data["current_operational_claim"])
        self.assertFalse(data["external_effect_authorized"])
        self.assertFalse(data["authority_inherited"])


if __name__ == "__main__":
    unittest.main()
