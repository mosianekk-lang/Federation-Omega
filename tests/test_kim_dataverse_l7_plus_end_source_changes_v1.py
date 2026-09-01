from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class EndSourceChangesTests(unittest.TestCase):
 def test_end(self): self.assertEqual('END_SOURCE_CHANGES',(ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_end_source_changes_v1.txt').read_text().strip())
if __name__=='__main__': unittest.main()
