import unittest,tempfile,shutil,pathlib,subprocess,csv,os,json
from fuse_genesis.forge_bootstrap import *

class T(unittest.TestCase):
 def setUp(self):
  self.d=pathlib.Path(tempfile.mkdtemp())
  self.src=self.d/"src"; self.src.mkdir()
  run(["git","init","-q"],cwd=self.src)
  run(["git","config","user.email","test@example.invalid"],cwd=self.src)
  run(["git","config","user.name","Test"],cwd=self.src)
  (self.src/"a.txt").write_text("a")
  run(["git","add","a.txt"],cwd=self.src); run(["git","commit","-q","-m","one"],cwd=self.src)
  self.c1=run(["git","rev-parse","HEAD"],cwd=self.src); self.t1=git_commit_tree(self.src,self.c1)
  (self.src/"b.txt").write_text("bb")
  run(["git","add","b.txt"],cwd=self.src); run(["git","commit","-q","-m","two"],cwd=self.src)
  self.c2=run(["git","rev-parse","HEAD"],cwd=self.src); self.t2=git_commit_tree(self.src,self.c2)
 def tearDown(self): shutil.rmtree(self.d,ignore_errors=True)
 def manifest_current(self):
  rows=ls_tree_entries(self.src,self.c2)
  return TreeManifest([TreeEntry(p,m,t,s,z,self.t2) for p,m,t,s,z in rows])
 def test_01_tree(self): self.assertEqual(len(self.t2),40)
 def test_02_object_exists(self): self.assertTrue(git_object_exists(self.src,self.c2))
 def test_03_manifest_validate(self): self.assertEqual(self.manifest_current().validate(expected_tree=self.t2)["total"],2)
 def test_04_manifest_tree_mismatch(self):
  with self.assertRaises(ValueError): self.manifest_current().validate(expected_tree="0"*40)
 def test_05_manifest_count_mismatch(self):
  with self.assertRaises(ValueError): self.manifest_current().validate(expected_total=3)
 def test_06_manifest_digest(self): self.assertEqual(len(self.manifest_current().digest()),64)
 def test_07_local_mirror(self):
  m=clone_local_mirror(self.src,self.d/"mirror.git"); self.assertEqual(run(["git","rev-parse","HEAD"],cwd=m),self.c2)
 def test_08_mirror_tree(self):
  m=clone_local_mirror(self.src,self.d/"mirror.git"); self.assertEqual(git_commit_tree(m,"HEAD"),self.t2)
 def test_09_refs_equal(self):
  m=clone_local_mirror(self.src,self.d/"mirror.git"); self.assertTrue(all(x["match"] for x in compare_refs(git_show_refs(self.src),git_show_refs(m))))
 def test_10_divergence(self):
  m=clone_local_mirror(self.src,self.d/"mirror.git"); a=git_show_refs(m); b=dict(a); b["refs/heads/x"]="0"*40
  self.assertFalse(all(x["match"] for x in compare_refs(a,b)))
 def test_11_bundle(self):
  b=make_bundle(self.src,self.d/"r.bundle"); self.assertTrue(verify_bundle(b))
 def test_12_bundle_clone(self):
  b=make_bundle(self.src,self.d/"r.bundle"); m=clone_bundle_mirror(b,self.d/"bm.git"); self.assertEqual(run(["git","rev-parse","HEAD"],cwd=m),self.c2)
 def test_13_bundle_tree(self):
  b=make_bundle(self.src,self.d/"r.bundle"); m=clone_bundle_mirror(b,self.d/"bm.git"); self.assertEqual(git_commit_tree(m,"HEAD"),self.t2)
 def test_14_manifest_repo_match(self): self.assertTrue(compare_manifest_to_repo(self.manifest_current(),self.src,self.c2)["match"])
 def test_15_manifest_repo_mismatch(self):
  m=self.manifest_current(); e=m.entries[0]; bad=TreeManifest([TreeEntry(e.path,e.mode,e.type,"0"*40,e.size,e.source_tree_sha),*m.entries[1:]])
  self.assertFalse(compare_manifest_to_repo(bad,self.src,self.c2)["match"])
 def test_16_gate_pass(self):
  c=GateCourt([GateResult(g,"PASS",g+"-ref") for g in REQUIRED_GATES]); self.assertTrue(c.verdict()["pass"])
 def test_17_gate_missing(self):
  c=GateCourt([GateResult("AIRLOCK","PASS","x")]); self.assertFalse(c.verdict()["pass"])
 def test_18_gate_fail(self):
  c=GateCourt([GateResult(g,"FAIL" if g=="AIRLOCK" else "PASS","x") for g in REQUIRED_GATES]); self.assertIn("AIRLOCK",c.verdict()["failed"])
 def test_19_gate_evidence(self):
  c=GateCourt([GateResult(g,"PASS","" if g=="BUBBLES" else "x") for g in REQUIRED_GATES]); self.assertIn("BUBBLES",c.verdict()["no_evidence"])
 def test_20_plan_no_bytes(self):
  p=ForgeBootstrapPlan(self.c2,self.t2,2,False,False,False); self.assertEqual(p.stage(),"MANIFEST_PARITY_READY_OBJECT_BYTES_OPEN")
 def test_21_plan_bytes_no_source(self):
  p=ForgeBootstrapPlan(self.c2,self.t2,2,True,False,False); self.assertEqual(p.stage(),"PRIVATE_MIRROR_CAN_BUILD_SOURCE_MUTATION_HELD")
 def test_22_plan_cutover_held(self):
  p=ForgeBootstrapPlan(self.c2,self.t2,2,True,True,False); self.assertEqual(p.stage(),"PRIVATE_MIRROR_SOURCE_GATES_READY_CUTOVER_HELD")
 def test_23_plan_eligible(self):
  p=ForgeBootstrapPlan(self.c2,self.t2,2,True,True,True); self.assertEqual(p.stage(),"CUTOVER_ELIGIBLE_PENDING_JUDGE")
 def test_24_receipt(self):
  r=source_parity_receipt(self.src,self.c2,self.c2,self.t2); self.assertTrue(r["commit_match"] and r["tree_match"])
 def test_25_receipt_bad(self):
  r=source_parity_receipt(self.src,self.c2,"0"*40,self.t2); self.assertFalse(r["commit_match"])
 def test_26_csv_roundtrip(self):
  p=self.d/"m.csv"
  with p.open("w",newline="") as f:
   w=csv.writer(f); w.writerow(["Path","Mode","Type","Git_Object_SHA","Size_Bytes","Source_Tree_SHA"])
   for e in self.manifest_current().entries: w.writerow([e.path,e.mode,e.type,e.object_sha,e.size or "",e.source_tree_sha])
  self.assertEqual(TreeManifest.from_csv(p).stats()["total"],2)
 def test_27_unsafe_path(self):
  e=TreeEntry("../x","100644","blob","0"*40,1,self.t2)
  with self.assertRaises(ValueError): TreeManifest([e]).validate()
 def test_28_duplicate_path(self):
  e=self.manifest_current().entries[0]
  with self.assertRaises(ValueError): TreeManifest([e,e]).validate()
 def test_29_bad_type(self):
  e=self.manifest_current().entries[0]; b=TreeEntry(e.path,e.mode,"bad",e.object_sha,e.size,e.source_tree_sha)
  with self.assertRaises(ValueError): TreeManifest([b]).validate()
 def test_30_bad_mode(self):
  e=self.manifest_current().entries[0]; b=TreeEntry(e.path,"999999",e.type,e.object_sha,e.size,e.source_tree_sha)
  with self.assertRaises(ValueError): TreeManifest([b]).validate()
 def test_31_bad_sha(self):
  e=self.manifest_current().entries[0]; b=TreeEntry(e.path,e.mode,e.type,"x",e.size,e.source_tree_sha)
  with self.assertRaises(ValueError): TreeManifest([b]).validate()
 def test_32_blob_size(self):
  e=self.manifest_current().entries[0]; b=TreeEntry(e.path,e.mode,"blob",e.object_sha,None,e.source_tree_sha)
  with self.assertRaises(ValueError): TreeManifest([b]).validate()
 def test_33_stats_blobs(self): self.assertEqual(self.manifest_current().stats()["blobs"],2)
 def test_34_stats_bytes(self): self.assertEqual(self.manifest_current().stats()["blob_bytes"],3)
 def test_35_commit_history_bundle(self):
  b=make_bundle(self.src,self.d/"r.bundle"); m=clone_bundle_mirror(b,self.d/"bm.git"); self.assertEqual(int(run(["git","rev-list","--count","HEAD"],cwd=m)),2)
 def test_36_local_only_missing(self):
  with self.assertRaises(FileNotFoundError): clone_local_mirror(self.d/"no",self.d/"x")
 def test_37_refs_shape(self): self.assertTrue(any(k.startswith("refs/heads/") for k in git_show_refs(self.src)))
 def test_38_ls_tree_count(self): self.assertEqual(len(ls_tree_entries(self.src,self.c2)),2)
 def test_39_required_gates(self): self.assertEqual(REQUIRED_GATES,("AIRLOCK","BUBBLES","LEAK_GUARD","PROOFOS"))
 def test_40_manifest_source_tree_single(self): self.assertEqual(self.manifest_current().validate()["tree"],self.t2)

if __name__=="__main__": unittest.main(verbosity=2)
