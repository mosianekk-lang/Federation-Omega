from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class CINowTests(unittest.TestCase):
 def test_ci_now(self): self.assertEqual('RUN_CI_NOW',(ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_ci_now_v1.txt').read_text().strip())
if __name__=='__main__': unittest.main()
