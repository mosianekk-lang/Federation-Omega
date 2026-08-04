from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from .prove_provider_dispatch_outcome_reconciliation_release import prove
class ReleaseProofTests(unittest.TestCase):
    def test_release_proof(self):
        with tempfile.TemporaryDirectory() as d:
            r=prove(Path(d))
            self.assertEqual(r['checks_failed'],0)
            self.assertEqual(r['checks_required'],15)
            self.assertEqual(r['provider_proof']['artifact_id'],8894094769)
            self.assertEqual(r['commercial_truth']['verified_live_revenue_events'],0)
            self.assertFalse(r['commercial_truth']['full_commercial_maturity'])
if __name__=='__main__': unittest.main()
