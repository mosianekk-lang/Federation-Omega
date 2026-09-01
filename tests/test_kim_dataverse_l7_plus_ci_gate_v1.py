from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class CIGateTests(unittest.TestCase):
 def test_gate(self): self.assertEqual('CI_GATE',(ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_ci_gate_v1.txt').read_text().strip())
if __name__=='__main__': unittest.main()
