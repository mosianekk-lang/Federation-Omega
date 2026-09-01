from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class AdmissionMarkerTests(unittest.TestCase):
    def test_marker(self):
        self.assertEqual("REPAIR_AND_ADMISSION_ONLY", (ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_admission_marker_v1.txt").read_text().strip())

if __name__ == "__main__":
    unittest.main()
