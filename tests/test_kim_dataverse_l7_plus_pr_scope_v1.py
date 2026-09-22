from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_pr_scope_v1.json"


class KimDataverseLevel7PlusPRScopeTests(unittest.TestCase):
    def test_pr_scope_is_no_effect_and_no_operational_overclaim(self) -> None:
        data = json.loads(SCOPE.read_text(encoding="utf-8"))
        self.assertFalse(data["expected_external_effect"])
        self.assertFalse(data["expected_provider_mutation"])
        self.assertFalse(data["expected_iam_wif_mutation"])
        self.assertFalse(data["operational_level7_claim"])


if __name__ == "__main__":
    unittest.main()
