from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ROOT / "benchmarking/cfbe_omega/kim_dataverse_level7_plus_done_criteria_v1.md"


class KimDataverseLevel7PlusDoneCriteriaTests(unittest.TestCase):
    def test_operational_level7_requires_newest_serving_phoenix_and_empirical_proof(self) -> None:
        text = CRITERIA.read_text(encoding="utf-8")
        self.assertIn("persistent continuation without chat-turn dependency", text)
        self.assertIn("prospective owner-value minimum", text)
        self.assertIn("provider-native readback", text)
        self.assertIn("newest serving-main Phoenix green", text)


if __name__ == "__main__":
    unittest.main()
