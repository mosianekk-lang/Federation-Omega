import os,tempfile,unittest
from bubbles.federation_learning_omega45 import OperationalLearningRuntime

class Omega45Tests(unittest.TestCase):
    def setUp(self): self.t=tempfile.TemporaryDirectory(); self.r=OperationalLearningRuntime(os.path.join(self.t.name,"l.sqlite3"))
    def tearDown(self): self.r.close(); self.t.cleanup()
    def _feed(self,n=12):
        for i in range(n):
            common=dict(project_id="TUT",mission_type="legal_email_review")
            self.r.observe(**common,metric="retrieval.calls",value=2+(i%2)); self.r.observe(**common,metric="context.hot1_bytes",value=9000+i*100); self.r.observe(**common,metric="stall.seconds_to_progress",value=300+i*5); self.r.observe(**common,metric="retrieval.result_tokens",value=2200+i*10); self.r.observe(**common,metric="latency.total_ms",value=600+i*10); self.r.observe(**common,metric="proof.completed",value=1); self.r.observe(**common,metric="reuse.prevented_call",value=1 if i%2==0 else 0)
    def test_refuses_unsafe_text_metric(self):
        with self.assertRaises(ValueError): self.r.observe(project_id="TUT",mission_type="x",metric="raw.email.body",value=1)
    def test_insufficient_evidence_stays_shadow(self):
        self._feed(5); x=self.r.propose("TUT","legal_email_review"); self.assertFalse(x["eligible"]); self.assertIn("SHADOW",x["state"])
    def test_policy_can_promote_only_after_evidence_and_shadow_gate(self):
        self._feed(16); x=self.r.promote_if_qualified("TUT","legal_email_review"); self.assertTrue(x["promoted"]); self.assertGreaterEqual(x["policy"]["sample_count"],12); self.assertIsNotNone(self.r.active_policy("TUT","legal_email_review"))

if __name__=="__main__": unittest.main()
