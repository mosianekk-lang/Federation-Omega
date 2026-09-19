from __future__ import annotations
import json,unittest
from federation.fuse_x_minimal_canary_v1 import *
class Fake:
    def whoami(self): return {"data":{"id":"u1","username":"owner"}}
    def home_one(self,uid): return {"data":[{"id":"p1","created_at":"2026-09-19T00:00:00Z","text":"not placed in receipt"}]}
class Tests(unittest.TestCase):
    def test_cost_estimate(self): self.assertEqual(estimated_variable_cost(),0.015)
    def test_cap_too_low(self):
        with self.assertRaisesRegex(CanaryError,"COST_CAP_TOO_LOW"): run_minimal_live_canary(Fake(),0.014)
    def test_receipt_minimal(self):
        r=run_minimal_live_canary(Fake()); self.assertTrue(r.authorized_user_present); self.assertEqual(r.home_post_count,1); self.assertEqual(r.write_effects,0); self.assertFalse(r.content_disclosed_in_receipt); self.assertEqual(r.estimated_resource_cost_usd,0.015)
    def test_no_post_text_in_receipt(self): self.assertNotIn("not placed",json.dumps(run_minimal_live_canary(Fake()).to_dict()))
    def test_user_missing(self):
        class X(Fake):
            def whoami(self): return {"data":{}}
        with self.assertRaisesRegex(CanaryError,"AUTHORIZED_USER_ID_MISSING"): run_minimal_live_canary(X())
    def test_home_missing(self):
        class X(Fake):
            def home_one(self,uid): return {"data":[]}
        with self.assertRaisesRegex(CanaryError,"HOME_TIMELINE_EMPTY"): run_minimal_live_canary(X())
    def test_schema(self): self.assertEqual(SCHEMA,"FUSE-X-MINIMAL-LIVE-CANARY-V1")
    def test_write_effects_zero(self): self.assertEqual(run_minimal_live_canary(Fake()).write_effects,0)
    def test_pricing_epoch(self): self.assertEqual(PRICING_EPOCH,"2026-09-19")
    def test_default_cap_bounded(self): self.assertLessEqual(DEFAULT_VARIABLE_COST_CAP_USD,0.02)
if __name__=="__main__": unittest.main()
