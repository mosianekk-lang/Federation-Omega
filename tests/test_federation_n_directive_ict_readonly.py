from __future__ import annotations
import copy, importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MOD_PATH=ROOT/"governance"/"federation_n_directive_ict_readonly.py"
SPEC=importlib.util.spec_from_file_location("ict",MOD_PATH);assert SPEC and SPEC.loader
M=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=M;SPEC.loader.exec_module(M)
PACKET=ROOT/"tests"/"fixtures"/"federation_n_ict_technical_packet.json"
def load():return json.loads(PACKET.read_text())
def refresh(s):s["fingerprint"]=M.digest({k:s.get(k) for k in ("id","type","title","files","claims")})
class ICTTests(unittest.TestCase):
 def test_valid(self):
  v=M.validate(load());self.assertTrue(v["passed"],v);self.assertEqual(v["evidence"]["source_count"],6);self.assertEqual(v["evidence"]["file_count"],12)
 def test_source_omission(self):
  p=load();p["sources"].pop();self.assertIn("SOURCE_COUNT",{x["code"] for x in M.validate(p)["violations"]})
 def test_hash_tamper(self):
  p=load();p["sources"][0]["files"][0]["sha256"]="0"*64;refresh(p["sources"][0]);self.assertIn("FILE_HASH",{x["code"] for x in M.validate(p)["violations"]})
 def test_duplicate_file(self):
  p=load();p["sources"][1]["files"].append(copy.deepcopy(p["sources"][1]["files"][0]));refresh(p["sources"][1]);self.assertIn("DUP_FILE",{x["code"] for x in M.validate(p)["violations"]})
 def test_authority_tamper(self):
  p=load();p["provider_mutation"]=True;self.assertIn("FIELD",{x["code"] for x in M.validate(p)["violations"]})
 def test_passport_release(self):
  x=M.build(load())["passport"];self.assertEqual(x["release"]["payload_files"],102);self.assertEqual(len(x["release"]["selected_files"]),12)
 def test_build_and_preflight(self):
  x=M.build(load())["passport"];self.assertEqual(x["build"]["non_root_uid"],65532);self.assertTrue(x["build"]["digest_build_args"]);self.assertFalse(x["preflight"]["mutation"]);self.assertEqual(x["preflight"]["mandate_state"],"TEMPLATE_NOT_ACTIVE")
 def test_private_deployment(self):
  x=M.build(load())["passport"]["deployment"];self.assertTrue(x["private_auth"]);self.assertTrue(x["zero_traffic"]);self.assertTrue(x["named_service_account"]);self.assertFalse(x["executed"])
 def test_state_canary_rollback(self):
  x=M.build(load())["passport"];self.assertEqual(x["state"]["schema"],"fevx_cse");self.assertTrue(x["state"]["idempotency_constraints"]);self.assertFalse(x["state"]["provider_connection"]);self.assertTrue(x["canary"]["self_certification_blocked"]);self.assertFalse(x["canary"]["executed"]);self.assertTrue(x["rollback"]["default_hold"]);self.assertFalse(x["rollback"]["executed"])
 def test_tensions_and_gaps(self):
  x=M.build(load());self.assertEqual(len(x["tensions"]),5);self.assertEqual(len(x["gaps"]),10);self.assertTrue(all(g["state"]=="UNVERIFIED_PENDING_PROVIDER_READBACK" for g in x["gaps"]))
 def test_routes_and_delta(self):
  x=M.build(load());self.assertEqual(set(x["formation"]["route_families"]),M.ROUTES);self.assertEqual(x["formation"]["selected"],"COMPOSE_OR_EXTEND");self.assertEqual(x["metrics"]["baseline"],"5/10");self.assertEqual(x["metrics"]["treatment"],"10/10");self.assertEqual(x["metrics"]["delta"],5)
 def test_no_effects(self):
  x=M.build(load());self.assertEqual(x["metrics"]["provider_mutations"],0);self.assertEqual(x["metrics"]["traffic_changes"],0);self.assertEqual(x["metrics"]["destructive_actions"],0);self.assertEqual(x["metrics"]["external_effects"],0)
 def test_deterministic(self):
  p=load();a=M.build(p);b=M.build(p);self.assertEqual(a,b);self.assertTrue(M.verify(a)["passed"])
 def test_tamper_and_overclaim(self):
  x=M.build(load());x["metrics"]["provider_mutations"]=1;self.assertIn("RECEIPT",{v["code"] for v in M.verify(x)["violations"]})
  x=M.build(load());x["release_claims"].append("Provider authority repaired and production live");z=copy.deepcopy(x);z.pop("receipt_sha256",None);x["receipt_sha256"]=M.digest(z);self.assertIn("OVERCLAIM",{v["code"] for v in M.verify(x)["violations"]})
 def test_cli(self):
  with tempfile.TemporaryDirectory() as d:
   o=Path(d)/"out.json";r=subprocess.run([sys.executable,str(MOD_PATH),"--packet",str(PACKET),"--output",str(o)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(json.loads(o.read_text())["verification"]["passed"])
if __name__=="__main__":unittest.main()
