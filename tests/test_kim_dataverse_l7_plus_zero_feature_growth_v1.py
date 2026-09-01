import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class ZeroGrowthTests(unittest.TestCase):
 def test_zero_growth(self):
  d=json.loads((ROOT/'benchmarking/cfbe_omega/kim_dataverse_l7_plus_zero_feature_growth_v1.json').read_text()); self.assertFalse(d['feature_growth']); self.assertEqual('ADMISSION_AND_REPAIR',d['phase'])
if __name__=='__main__': unittest.main()
