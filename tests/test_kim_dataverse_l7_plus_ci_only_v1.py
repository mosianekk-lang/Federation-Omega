from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class CIOnlyTests(unittest.TestCase):
 def test_ci_only(self): self.assertEqual('CI_ONLY',(ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_ci_only_v1.txt').read_text().strip())
if __name__=='__main__': unittest.main()
