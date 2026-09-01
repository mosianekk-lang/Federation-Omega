from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_market_sources_v1.json"


class KimDataverseLevel7PlusMarketSourceTests(unittest.TestCase):
    def test_market_harvest_is_pattern_only_and_makes_no_vendor_superiority_claim(self) -> None:
        data = json.loads(SOURCES.read_text(encoding="utf-8"))
        self.assertEqual("PUBLIC_ARCHITECTURAL_PATTERNS_ONLY", data["harvest_policy"])
        self.assertFalse(data["vendor_superiority_claim"])
        self.assertFalse(data["proprietary_source_harvested"])


if __name__ == "__main__":
    unittest.main()
