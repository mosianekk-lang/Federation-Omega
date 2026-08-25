import json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parent; sys.path.insert(0,str(ROOT)); import bootstrap_wif as b
class BootstrapTests(unittest.TestCase):
  def setUp(self): self.c=b.load_config(ROOT/"wif_config.json")
  def test_repo_id(self): self.assertIn("repository_id=='1292795464'",b.condition(self.c))
  def test_owner_id(self): self.assertIn("repository_owner_id=='261966700'",b.condition(self.c))
  def test_main_only(self): self.assertIn("refs/heads/main",b.condition(self.c))
  def test_dispatch_only(self): self.assertIn("workflow_dispatch",b.condition(self.c))
  def test_default_audience(self): self.assertFalse(any("--allowed-audiences" in x for cmd in b.commands(self.c) for x in cmd))
  def test_keyless(self): self.assertFalse(any("keys" in x for cmd in b.commands(self.c) for x in cmd))
  def test_dry_run_zero_effect(self): self.assertEqual([],b.run(self.c,False)["executed"])
  def test_deterministic(self): self.assertEqual(b.run(self.c,False),b.run(self.c,False))
  def test_manifest_hash_is_exact(self): self.assertEqual(64,len(self.c["manifestSha256"]))
  def test_provider_readback_accepts_exact_contract(self):
    value={"oidc":{"issuerUri":self.c["issuerUri"]},"attributeCondition":b.condition(self.c),"attributeMapping":{x.split("=",1)[0]:x.split("=",1)[1] for x in b.mapping().split(",")},"state":"ACTIVE"}
    self.assertIsNone(b.verify_provider(self.c,value))
  def test_provider_readback_rejects_drift(self):
    with self.assertRaises(b.BootstrapError): b.verify_provider(self.c,{"oidc":{"issuerUri":"https://example.invalid"}})
  def test_operator_account(self): self.assertTrue(any(self.c["operatorServiceAccount"] in cmd for cmd in b.commands(self.c)))
  def test_apis(self): self.assertTrue(set(b.APIS).issubset(set(b.commands(self.c)[0])))
  def test_bad_hash(self):
    v=dict(self.c); v["sourceSha256"]="bad"; p=ROOT/"_bad.json"; p.write_text(json.dumps(v))
    try:
      with self.assertRaises(b.BootstrapError): b.load_config(p)
    finally: p.unlink()
if __name__=="__main__": unittest.main()
