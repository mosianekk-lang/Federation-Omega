from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class FinalFreezeTests(unittest.TestCase):
    def test_final_freeze(self):
        self.assertEqual("NO_MORE_FEATURE_FILES_AFTER_THIS_POINT", (ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_final_freeze_v1.txt").read_text().strip())
if __name__ == "__main__": unittest.main()
