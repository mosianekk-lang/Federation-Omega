from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class AdmissionPhaseTests(unittest.TestCase):
    def test_ci_repair_only(self):
        self.assertEqual("CI_REPAIR_ONLY", (ROOT / "benchmarking/cfbe_omega/kim_dataverse_l7_plus_admission_phase_v1.txt").read_text().strip())
if __name__ == "__main__": unittest.main()
