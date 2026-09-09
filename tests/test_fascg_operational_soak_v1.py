import unittest
from benchmarking.cfbe_omega.fascg_operational_soak_v1 import (
    PROVIDER_EFFECT_AUTHORIZED, OPERATIONAL_VERIFIED, SUSTAINED_VALUE_VERIFIED, TEN_X_VERIFIED,
    OperationalWindow, OperationalSoakCourt,
)
from benchmarking.cfbe_omega.fascg_production_runtime_v1 import ProductionStage

SHA='a'*40

def w(i,t,**kw):
    body=dict(window_id=f'w{i}',source_sha=SHA,run_id=f'r{i}',observed_at_epoch=t,provider_native_readback=True,health_verified=True,persistence_verified=True,rollback_verified=True,state_lineage_valid=True,safety_score=.99,reliability_score=.99,owner_value_score=.8,critical_incidents=0,proof_refs=(f'p{i}',))
    body.update(kw); return OperationalWindow(**body)

class SoakTests(unittest.TestCase):
    def setUp(self): self.c=OperationalSoakCourt(); self.rows=(w(1,0),w(2,150),w(3,300))
    def test_truth_flags(self):
        self.assertFalse(PROVIDER_EFFECT_AUTHORIZED); self.assertFalse(OPERATIONAL_VERIFIED); self.assertFalse(SUSTAINED_VALUE_VERIFIED); self.assertFalse(TEN_X_VERIFIED)
    def test_three_window_operational_soak(self):
        r=self.c.evaluate(self.rows); self.assertEqual(r.status,'OPERATIONAL_EVIDENCE_ELIGIBLE'); self.assertEqual(r.promotion_evidence.stage,ProductionStage.OPERATIONAL)
    def test_time_span_floor_blocks(self):
        r=self.c.evaluate((w(1,0),w(2,10),w(3,20))); self.assertIn('SOAK_TIME_SPAN_FLOOR',r.blockers)
    def test_provider_readback_missing_blocks(self):
        r=self.c.evaluate((w(1,0),w(2,150,provider_native_readback=False),w(3,300))); self.assertIn('PROVIDER_READBACK_REQUIRED',r.blockers)
    def test_source_drift_blocks(self):
        r=self.c.evaluate((w(1,0),w(2,150,source_sha='b'*40),w(3,300))); self.assertIn('SOURCE_DRIFT',r.blockers)
    def test_critical_incident_blocks(self):
        r=self.c.evaluate((w(1,0),w(2,150,critical_incidents=1),w(3,300))); self.assertIn('CRITICAL_INCIDENT_PRESENT',r.blockers)
    def test_sustained_value_requires_longer_span(self):
        r=self.c.evaluate(self.rows,sustained_value=True); self.assertIn('SOAK_TIME_SPAN_FLOOR',r.blockers)
    def test_sustained_value_passes_real_span_and_value(self):
        rows=(w(1,0),w(2,450),w(3,900)); r=self.c.evaluate(rows,sustained_value=True)
        self.assertEqual(r.status,'SUSTAINED_VALUE_EVIDENCE_ELIGIBLE'); self.assertEqual(r.promotion_evidence.stage,ProductionStage.SUSTAINED_VALUE); self.assertEqual(r.promotion_evidence.sustained_windows,3)
    def test_owner_value_floor_blocks_sustained(self):
        rows=(w(1,0,owner_value_score=.5),w(2,450,owner_value_score=.5),w(3,900,owner_value_score=.5)); r=self.c.evaluate(rows,sustained_value=True)
        self.assertIn('OWNER_VALUE_FLOOR_FAILED',r.blockers)
    def test_run_reuse_blocks_independence(self):
        rows=(w(1,0),w(2,150,run_id='r1'),w(3,300)); r=self.c.evaluate(rows); self.assertIn('RUN_ID_REUSE',r.blockers)

if __name__=='__main__': unittest.main()
