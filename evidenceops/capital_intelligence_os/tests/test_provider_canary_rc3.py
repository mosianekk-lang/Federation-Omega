import tempfile
import unittest
from pathlib import Path
from evidenceops.capital_intelligence_os.provider_canary import ProviderCanary,ProviderCanarySpec
SHA="a"*40
def verified_release(): return {"passed":True,"release":"1.0.0-rc2"}
def failed_release(): return {"passed":False,"release":"1.0.0-rc2"}
class ProviderCanaryRC3Tests(unittest.TestCase):
 def spec(self,path): return ProviderCanarySpec(SHA,SHA,"runtime-identity","tenant-canary",path)
 def test_persistent_canary_passes(self):
  with tempfile.TemporaryDirectory() as td:
   r=ProviderCanary(release_verify=verified_release).run(self.spec(str(Path(td)/"canary.db"))); self.assertTrue(r.passed); self.assertTrue(r.validate_digest())
 def test_memory_database_is_rejected(self):
  with self.assertRaises(ValueError): self.spec(":memory:").validate()
 def test_source_mismatch_is_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError): ProviderCanarySpec("a"*40,"b"*40,"runtime-identity","tenant-canary",str(Path(td)/"canary.db")).validate()
 def test_release_failure_blocks_canary_pass(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertFalse(ProviderCanary(release_verify=failed_release).run(self.spec(str(Path(td)/"canary.db"))).passed)
 def test_receipt_contains_nonempty_digest(self):
  with tempfile.TemporaryDirectory() as td:
   self.assertEqual(len(ProviderCanary(release_verify=verified_release).run(self.spec(str(Path(td)/"canary.db"))).receipt_digest),64)
