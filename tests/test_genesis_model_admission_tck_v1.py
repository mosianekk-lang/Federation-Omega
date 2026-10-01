import unittest
from fuse_genesis.model_admission import *

S="a"*64
def model(**kw):
 d=dict(model_id="q",family="qwen",format="GGUF",sha256=S,size_bytes=1*1024**3,quantization="Q4",context_tokens=4096,license_id="Apache-2.0",source_ref="src",capabilities=("reason","code"))
 d.update(kw); return ModelArtifact(**d)
def hw(**kw):
 d=dict(host_id="h",ram_total_bytes=16*1024**3,ram_available_bytes=12*1024**3,vram_total_bytes=8*1024**3,vram_available_bytes=6*1024**3,cpu_threads=8,gpu_name="g",disk_free_bytes=100*1024**3)
 d.update(kw); return HardwareDescriptor(**d)

class T(unittest.TestCase):
 def test_01_model(self): self.assertEqual(model().validate(),model())
 def test_02_bad_sha(self):
  with self.assertRaises(ValueError): model(sha256="x").validate()
 def test_03_format(self):
  with self.assertRaises(ValueError): model(format="bin").validate()
 def test_04_license(self):
  with self.assertRaises(ValueError): model(license_id="").validate()
 def test_05_caps(self):
  with self.assertRaises(ValueError): model(capabilities=()).validate()
 def test_06_hw(self): self.assertEqual(hw().validate().host_id,"h")
 def test_07_hw_ram(self):
  with self.assertRaises(ValueError): hw(ram_available_bytes=20*1024**3).validate()
 def test_08_fit(self): self.assertTrue(evaluate_fit(model(),hw()).admitted)
 def test_09_low_ram(self): self.assertIn("INSUFFICIENT_RAM",evaluate_fit(model(size_bytes=10*1024**3),hw(ram_available_bytes=3*1024**3)).reasons)
 def test_10_low_disk(self): self.assertIn("INSUFFICIENT_DISK",evaluate_fit(model(size_bytes=10*1024**3),hw(disk_free_bytes=1*1024**3)).reasons)
 def test_11_route_gpu(self): self.assertEqual(evaluate_fit(model(),hw()).route,"GPU_FULL")
 def test_12_route_cpu(self): self.assertEqual(evaluate_fit(model(size_bytes=7*1024**3),hw(vram_available_bytes=1)).route,"CPU_OR_PARTIAL_GPU")
 def test_13_kv(self): self.assertGreater(evaluate_fit(model(),hw()).estimated_kv_bytes,0)
 def test_14_disk_mult(self): self.assertGreater(evaluate_fit(model(),hw()).required_disk_bytes,model().size_bytes)
 def test_15_probe(self): self.assertTrue(RuntimeProbe("q",S,"ollama","1","h",True,True,1,1,1.0,"t").qualifies())
 def test_16_probe_load(self): self.assertFalse(RuntimeProbe("q",S,"ollama","1","h",False,True,1,1,1.0,"t").qualifies())
 def test_17_probe_api(self): self.assertFalse(RuntimeProbe("q",S,"ollama","1","h",True,False,1,1,1.0,"t").qualifies())
 def test_18_ctx_compare(self):
  a=BenchmarkContext("t",S,"h","r",S,"cold"); b=BenchmarkContext("t",S,"h","r","b"*64,"cold"); self.assertTrue(a.comparable(b))
 def test_19_ctx_hw(self):
  a=BenchmarkContext("t",S,"h","r",S,"cold"); b=BenchmarkContext("t",S,"x","r","b"*64,"cold"); self.assertFalse(a.comparable(b))
 def test_20_winner_chal(self):
  c=BenchmarkContext("t",S,"h","r",S,"cold"); d=BenchmarkContext("t",S,"h","r","b"*64,"cold")
  self.assertEqual(winner(BenchmarkResult(c,True,1,100,10,0),BenchmarkResult(d,True,1,80,10,0)),"CHALLENGER")
 def test_21_winner_quality(self):
  c=BenchmarkContext("t",S,"h","r",S,"cold"); d=BenchmarkContext("t",S,"h","r","b"*64,"cold")
  self.assertEqual(winner(BenchmarkResult(c,True,1,100,10,0),BenchmarkResult(d,True,.9,50,20,0)),"INCUMBENT")
 def test_22_not_compare(self):
  c=BenchmarkContext("t",S,"h","r",S,"cold"); d=BenchmarkContext("x",S,"h","r","b"*64,"cold")
  self.assertEqual(winner(BenchmarkResult(c,True,1,100,10,0),BenchmarkResult(d,True,1,50,20,0)),"NOT_COMPARABLE")
 def test_23_tie_inc(self):
  c=BenchmarkContext("t",S,"h","r",S,"cold"); d=BenchmarkContext("t",S,"h","r","b"*64,"cold")
  self.assertEqual(winner(BenchmarkResult(c,True,1,100,10,0),BenchmarkResult(d,True,1,100,10,0)),"INCUMBENT")
 def test_24_load_policy(self): self.assertEqual(LoadPolicy().choose_resident([("b",1,2),("a",2,1)]),("a",))
 def test_25_load_two(self): self.assertEqual(len(LoadPolicy(2).choose_resident([("a",1,1),("b",1,2),("c",0,9)])),2)
 def test_26_receipt_no_probe(self): self.assertFalse(admission_receipt(model(),hw(),evaluate_fit(model(),hw()),None)["complete"])
 def test_27_receipt_probe(self):
  p=RuntimeProbe("q",S,"ollama","1","h",True,True,1,1,1.0,"t"); self.assertTrue(admission_receipt(model(),hw(),evaluate_fit(model(),hw()),p)["complete"])
 def test_28_context_tokens(self): self.assertEqual(model().context_tokens,4096)
 def test_29_quant(self): self.assertEqual(model().quantization,"Q4")
 def test_30_license_in_receipt(self): self.assertEqual(admission_receipt(model(),hw(),evaluate_fit(model(),hw()),None)["model"]["license_id"],"Apache-2.0")
 def test_31_reserve_blocks(self):
  p=FitPolicy(ram_reserve_bytes=11*1024**3); self.assertFalse(evaluate_fit(model(),hw(),p).admitted)
 def test_32_no_gpu_optional(self):
  p=FitPolicy(gpu_offload_optional=False); self.assertEqual(evaluate_fit(model(),hw(vram_available_bytes=1),p).route,"CPU")
 def test_33_bad_source(self):
  with self.assertRaises(ValueError): model(source_ref="").validate()
 def test_34_bad_size(self):
  with self.assertRaises(ValueError): model(size_bytes=0).validate()
 def test_35_bad_ctx(self):
  with self.assertRaises(ValueError): model(context_tokens=0).validate()
 def test_36_model_caps_set(self): self.assertIn("reason",model().capabilities)
 def test_37_policy_idle(self): self.assertEqual(LoadPolicy().unload_idle_seconds,300)
 def test_38_probe_model_hash(self): self.assertEqual(RuntimeProbe("q",S,"x","1","h",True,True,1,1,1,"t").artifact_sha256,S)
 def test_39_owner_intervention_not_winner_shortcut(self):
  c=BenchmarkContext("t",S,"h","r",S,"cold"); d=BenchmarkContext("t",S,"h","r","b"*64,"cold")
  self.assertEqual(winner(BenchmarkResult(c,True,1,100,10,0),BenchmarkResult(d,True,1,80,9,5)),"INCUMBENT")
 def test_40_format_case(self): self.assertEqual(model(format="gguf").validate(),model(format="gguf"))
if __name__=="__main__": unittest.main(verbosity=2)
