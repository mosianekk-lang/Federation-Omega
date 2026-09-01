from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class NoopMarkerTests(unittest.TestCase):
 def test_noop(self): self.assertEqual('NOOP',(ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_noop_marker_v1.txt').read_text().strip())
if __name__=='__main__': unittest.main()
