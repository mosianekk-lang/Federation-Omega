from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class HaltCommitsTests(unittest.TestCase):
 def test_halt(self): self.assertEqual('NO_MORE_COMMITS_BEFORE_CI',(ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_no_more_commits_before_ci_v1.txt').read_text().strip())
if __name__=='__main__': unittest.main()
