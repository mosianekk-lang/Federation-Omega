import unittest
from fuse_genesis.creative_tck import *
S="a"*64
def intent(**kw):
 d=dict(intent_id="i",modalities=("image",),editable_master_required=True,provenance_required=True,target_fidelity="HIGH",dimensions=(1024,1024),duration_s=None)
 d.update(kw); return CreativeIntent(**d)
def cell(**kw):
 d=dict(cell_id="local-image",engine_class="RASTER_GENERATE",executable_ref="bin:local",version="1",local=True,modalities=("image",),editable_outputs=True,deterministic_seed=True,offline_capable=True,provenance_capable=True,max_width=4096,max_height=4096,max_duration_s=None,license_id="GPL-3.0",source_ref="src")
 d.update(kw); return CreativeCellDescriptor(**d)
def receipt(**kw):
 d=dict(artifact_id="a",logical_role="master",media_type="image/png",sha256=S,editable=True,provenance_ref="p",source_asset_refs=(),engine_cell_id="local-image",engine_version="1",intent_id="i")
 d.update(kw); return ArtifactReceipt(**d)
class T(unittest.TestCase):
 def test_01_intent(self): self.assertEqual(intent().validate(),intent())
 def test_02_intent_fidelity(self):
  with self.assertRaises(ValueError): intent(target_fidelity="X").validate()
 def test_03_dims(self):
  with self.assertRaises(ValueError): intent(dimensions=(0,1)).validate()
 def test_04_cell(self): self.assertEqual(cell().validate(),cell())
 def test_05_license(self):
  with self.assertRaises(ValueError): cell(license_id="").validate()
 def test_06_fit(self): self.assertTrue(qualify_cell(intent(),cell()).eligible)
 def test_07_modality(self): self.assertIn("MODALITY_GAP",qualify_cell(intent(modalities=("video",)),cell()).reasons)
 def test_08_editable(self): self.assertIn("EDITABLE_MASTER_GAP",qualify_cell(intent(),cell(editable_outputs=False)).reasons)
 def test_09_provenance(self): self.assertIn("PROVENANCE_GAP",qualify_cell(intent(),cell(provenance_capable=False)).reasons)
 def test_10_width(self): self.assertIn("WIDTH_LIMIT",qualify_cell(intent(dimensions=(8192,100)),cell()).reasons)
 def test_11_height(self): self.assertIn("HEIGHT_LIMIT",qualify_cell(intent(dimensions=(100,8192)),cell()).reasons)
 def test_12_duration(self): self.assertIn("DURATION_LIMIT",qualify_cell(intent(modalities=("video",),duration_s=20,dimensions=None),cell(modalities=("video",),max_duration_s=10)).reasons)
 def test_13_local_score(self): self.assertGreater(qualify_cell(intent(),cell()).score,qualify_cell(intent(),cell(local=False)).score)
 def test_14_choose(self): self.assertEqual(choose_cell(intent(),[cell(),cell(cell_id="x",local=False)])[0].cell_id,"local-image")
 def test_15_no_choose(self): self.assertIsNone(choose_cell(intent(modalities=("video",)),[cell()])[0])
 def test_16_receipt(self): self.assertEqual(receipt().validate(intent()),receipt())
 def test_17_bad_sha(self):
  with self.assertRaises(ValueError): receipt(sha256="x").validate(intent())
 def test_18_receipt_editable(self):
  with self.assertRaises(ValueError): receipt(editable=False).validate(intent())
 def test_19_receipt_prov(self):
  with self.assertRaises(ValueError): receipt(provenance_ref="").validate(intent())
 def test_20_binding(self):
  with self.assertRaises(ValueError): receipt(intent_id="x").validate(intent())
 def test_21_defects(self):
  d=DefectMap("a",(Defect("d","face","anatomy",2,"face"),Defect("e","bg","noise",1,"background"))); self.assertEqual(d.targeted_components(),("background","face"))
 def test_22_targeted(self):
  d=DefectMap("a",(Defect("d","x","x",1,"face"),)); self.assertFalse(compile_rerender(d).full_rerender)
 def test_23_full(self):
  d=DefectMap("a",(Defect("d","x","x",5,"face"),)); self.assertTrue(compile_rerender(d).full_rerender)
 def test_24_qc_accept(self): self.assertTrue(qc(intent(),receipt(),fidelity=.95,technical_valid=True).accepted)
 def test_25_qc_quality(self): self.assertFalse(qc(intent(),receipt(),fidelity=.85,technical_valid=True).accepted)
 def test_26_qc_technical(self): self.assertFalse(qc(intent(),receipt(),fidelity=.95,technical_valid=False).accepted)
 def test_27_master_threshold(self): self.assertFalse(qc(intent(target_fidelity="MASTER"),receipt(),fidelity=.96,technical_valid=True).accepted)
 def test_28_draft_threshold(self): self.assertTrue(qc(intent(target_fidelity="DRAFT"),receipt(),fidelity=.7,technical_valid=True).accepted)
 def test_29_probe(self): self.assertTrue(RuntimeProbe("c","1",S,"h",True,True,"t").qualifies())
 def test_30_probe_callable(self): self.assertFalse(RuntimeProbe("c","1",S,"h",False,True,"t").qualifies())
 def test_31_probe_sha(self): self.assertFalse(RuntimeProbe("c","1","x","h",True,True,"t").qualifies())
 def test_32_admission_no_probe(self): self.assertFalse(admission_receipt(cell(),None)["runtime_qualified"])
 def test_33_admission_probe(self): self.assertTrue(admission_receipt(cell(),RuntimeProbe("c","1",S,"h",True,True,"t"))["runtime_qualified"])
 def test_34_video_cell(self): self.assertTrue(qualify_cell(intent(modalities=("video",),dimensions=None,duration_s=3),cell(modalities=("video",),max_duration_s=5)).eligible)
 def test_35_vector_editable(self): self.assertTrue(qualify_cell(intent(modalities=("vector",),dimensions=None),cell(modalities=("vector",))).eligible)
 def test_36_audio(self): self.assertTrue(qualify_cell(intent(modalities=("audio",),dimensions=None,duration_s=2),cell(modalities=("audio",),max_duration_s=10)).eligible)
 def test_37_3d(self): self.assertTrue(qualify_cell(intent(modalities=("3d",),dimensions=None),cell(modalities=("3d",))).eligible)
 def test_38_source_assets(self): self.assertEqual(receipt(source_asset_refs=("x","y")).source_asset_refs,("x","y"))
 def test_39_offline_score(self): self.assertGreater(qualify_cell(intent(),cell(offline_capable=True)).score,qualify_cell(intent(),cell(offline_capable=False)).score)
 def test_40_deterministic_score(self): self.assertGreater(qualify_cell(intent(),cell(deterministic_seed=True)).score,qualify_cell(intent(),cell(deterministic_seed=False)).score)
if __name__=="__main__": unittest.main(verbosity=2)
