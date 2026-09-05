from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_readme_v1.md"


class KimDataverseLevel7PlusReadmeTests(unittest.TestCase):
    def test_readme_does_not_claim_operational_level7(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("does **not** claim that Level 7 is operationally achieved", text)
        self.assertIn("provider-native evidence", text)


if __name__ == "__main__":
    unittest.main()
