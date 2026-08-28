from __future__ import annotations
import io, unittest
from federation.living_state.ingress import INGRESS_SCHEMA, run_ingress_canary
class LivingIngressAirlockTests(unittest.TestCase):
    def test_schema(self): self.assertEqual(INGRESS_SCHEMA,"FEDERATION-LIVING-STATE-INGRESS-V1")
    def test_focused_suite(self):
        suite=unittest.defaultTestLoader.discover("federation/living_state/tests",pattern="test_*.py"); stream=io.StringIO(); r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite); self.assertTrue(r.wasSuccessful(),"LIVING_INGRESS_REGRESSION_FAILED\n"+stream.getvalue())
    def test_canary(self):
        r=run_ingress_canary(); self.assertEqual(r["status"],"PASS"); self.assertEqual(r["count"],7); self.assertTrue(all(r["checks"].values())); self.assertEqual(r["external_effects"],0)
    def test_truth_boundary(self):
        t=run_ingress_canary()["truth_boundary"]; self.assertTrue(t["host_invoked_not_background_daemon"]); self.assertTrue(t["exactly_once_is_store_scoped_transactional"]); self.assertTrue(t["private_payload_not_returned_in_receipt"]); self.assertFalse(t["external_effect_authority_created"])
if __name__=="__main__": unittest.main()
