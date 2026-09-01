from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class StopBuildingTests(unittest.TestCase):
    def test_stop_building(self):
        self.assertEqual("STOP_BUILDING_RUN_CI", (ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_stop_building_v1.txt").read_text().strip())
if __name__ == "__main__": unittest.main()
