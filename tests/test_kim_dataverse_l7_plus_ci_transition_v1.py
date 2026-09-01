from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class CITransitionTests(unittest.TestCase):
 def test_closed(self): self.assertEqual('SOURCE_STREAM_CLOSED',(ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_ci_transition_v1.txt').read_text().strip())
if __name__=='__main__': unittest.main()
