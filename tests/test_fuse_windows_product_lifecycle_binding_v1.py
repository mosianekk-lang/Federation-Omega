import hashlib, json, pathlib, re, unittest, zipfile, yaml
ROOT=pathlib.Path(__file__).resolve().parents[1]
WF=ROOT/'.github/workflows/fuse-windows-execution-plane-v1.yml'
GOV=ROOT/'governance/fuse_windows_execution_plane_v1.json'
COURT=ROOT/'product/windows_lifecycle/FUSE_TwoVersion_Windows_Lifecycle_Court_R10.zip'
EXPECTED='55dec3033c284f0329fba4d4059d7749eaebf4fca408648dd83d000f69445a2a'
R9='be02fba0a9f794d775e563eabefc01412f5975fee6dc12ae56b1060ae67a3979'
R10='63fc293db2dd945aa60943a3ec3b87d9230d171c3b5b76087aa0feb5ef9d1c18'
class CourtBinding(unittest.TestCase):
 def setUp(self):
  self.w=WF.read_text(); self.g=json.loads(GOV.read_text())
 def test_sealed_court_hash(self): self.assertEqual(hashlib.sha256(COURT.read_bytes()).hexdigest(),EXPECTED)
 def test_nested_package_hashes(self):
  with zipfile.ZipFile(COURT) as z:
   self.assertEqual(hashlib.sha256(z.read('packages/FUSE_Portable_PerUser_Lifecycle_R9.zip')).hexdigest(),R9)
   self.assertEqual(hashlib.sha256(z.read('packages/FUSE_Portable_PerUser_Lifecycle_R10.zip')).hexdigest(),R10)
 def test_court_crc(self):
  with zipfile.ZipFile(COURT) as z: self.assertIsNone(z.testzip())
 def test_no_arbitrary_task_input(self): self.assertIn('options: [health, inventory, hash_workspace_file, product_lifecycle_court]',self.w)
 def test_court_hash_bound_in_workflow(self): self.assertIn(EXPECTED,self.w)
 def test_permissions_read_only(self):
  self.assertRegex(self.w,r'permissions:\s*\n\s+contents: read')
  self.assertNotRegex(self.w,r'(?m)^\s*(id-token|actions|packages|deployments|issues|pull-requests):\s*write')
 def test_no_secret_context(self): self.assertNotIn('secrets.',self.w)
 def test_no_oidc(self): self.assertNotIn('id-token:',self.w)
 def test_no_network_or_provider_cli(self):
  for x in ['Invoke-WebRequest','curl ','gcloud ','az ','aws ','gh api','update-traffic','add-iam-policy-binding']:
   self.assertNotIn(x,self.w)
 def test_immutable_actions(self):
  for ref in re.findall(r'uses:\s*([^\s]+)',self.w):
   self.assertRegex(ref,r'^[^@]+@[0-9a-f]{40}$')
 def test_checkout_credentials_disabled(self): self.assertIn('persist-credentials: false',self.w)
 def test_concurrency_present(self): self.assertIn('concurrency:',self.w)
 def test_windows_native_runner(self): self.assertIn('runs-on: windows-latest',self.w)
 def test_receipt_truth_boundary(self):
  self.assertIn("HOSTED_WINDOWS_GITHUB_ACTIONS",self.w); self.assertIn('HOSTED_RUN_MUST_NOT_PROVE_OWNER_PC',self.w); self.assertIn('HOSTED_RUN_MUST_NOT_PROVE_SIGNING',self.w)
 def test_full_lifecycle_steps_bound(self):
  for s in ['R9_INSTALL','R9_VERIFY','R9_CORRUPT_EXPECT_VERIFY_FAIL','R9_REPAIR','R10_UPGRADE','R10_VERIFY','R10_ROLLBACK','R9_VERIFY_AFTER_ROLLBACK','R10_UPGRADE_AGAIN','R10_VERIFY_AGAIN','R10_UNINSTALL']:
   self.assertIn(s,self.w)
 def test_residue_gate(self): self.assertIn('FUSE_INSTALL_RESIDUE_PRESENT',self.w)
 def test_governance_default_stays_read_only(self): self.assertEqual(self.g['task_effect_ceiling'],'READ_ONLY')
 def test_special_task_is_local_reversible_only(self):
  c=self.g['specialized_task_contracts']['product_lifecycle_court']; self.assertEqual(c['effect_ceiling'],'LOCAL_REVERSIBLE_DISPOSABLE_HOST_USER_SCOPE'); self.assertFalse(c['owner_pc_proven']); self.assertFalse(c['code_signing_proven'])
 def test_no_provider_effect(self): self.assertEqual(self.g['provider_effect'],'NONE_UNTIL_SEPARATELY_AUTHORIZED')
 def test_no_arbitrary_command_execution(self): self.assertFalse(self.g['arbitrary_command_execution'])
 def test_yaml_parses(self):
  obj=yaml.safe_load(self.w); self.assertIsInstance(obj,dict); self.assertIn('jobs',obj)
 def test_no_secret_like_payload(self):
  blobs=[self.w,GOV.read_text(),(ROOT/'release/SOURCE_ADMISSION_HANDOFF.json').read_text(),(ROOT/'release/formation_routes.json').read_text()]
  pat=re.compile(r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"\']?[A-Za-z0-9_\-/.+=]{16,}')
  for b in blobs: self.assertIsNone(pat.search(b))
if __name__=='__main__': unittest.main(verbosity=2)
