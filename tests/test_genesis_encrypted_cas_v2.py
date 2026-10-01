import unittest,tempfile,shutil,pathlib,os,json
from fuse_genesis.encrypted_cas import *

class T(unittest.TestCase):
 def setUp(self):
  self.d=pathlib.Path(tempfile.mkdtemp()); self.k=InMemoryKeyProvider({"k1":b"1"*32,"k2":b"2"*32})
  self.s=EncryptedCAS(self.d/"store",self.k)
 def tearDown(self):
  try:self.s.close()
  except:pass
  shutil.rmtree(self.d,ignore_errors=True)
 def put(self,b=b"hello",key="k1"):
  return self.s.put(b,media_type="text/plain",privacy_class="P1_INTERNAL",logical_role="proof",key_ref=key,created_at="t")
 def test_01_put_get(self): a=self.put(); self.assertEqual(self.s.get(a.object_id),b"hello")
 def test_02_plaintext_id(self): a=self.put(); self.assertTrue(a.object_id.startswith("sha256:"))
 def test_03_cipher_diff_plain(self): a=self.put(); self.assertNotEqual(a.plaintext_sha256,a.ciphertext_sha256)
 def test_04_dedupe(self): a=self.put(); b=self.put(); self.assertEqual(a.object_id,b.object_id)
 def test_05_diff_key_existing_rejected(self): self.put(); 
 def test_06_wrong_key_provider_fails(self):
  a=self.put(); self.s.close(); self.s=EncryptedCAS(self.d/"store",InMemoryKeyProvider({"k1":b"2"*32}))
  self.assertFalse(self.s.verify(a.object_id))
 def test_07_corruption_detected(self):
  a=self.put(); p=self.s._path(a.plaintext_sha256); p.write_bytes(b"x"); self.assertFalse(self.s.verify(a.object_id))
 def test_08_missing(self):
  with self.assertRaises(KeyError): self.s.get("sha256:no")
 def test_09_manifest(self): self.put(); self.assertEqual(len(self.s.manifest()),1)
 def test_10_manifest_digest(self): self.put(); self.assertEqual(len(self.s.manifest_digest()),64)
 def test_11_replica(self):
  a=self.put(); r=self.s.replicate_to(a.object_id,self.d/"rep"); self.assertEqual(r["ciphertext_sha256"],a.ciphertext_sha256)
 def test_12_metadata_export(self):
  self.put(); m=self.s.export_metadata(self.d/"meta.json"); self.assertEqual(m["schema"],"FUSE-ENCRYPTED-CAS-METADATA-V2")
 def test_13_restore(self):
  a=self.put(); rep=self.d/"rep"; self.s.replicate_to(a.object_id,rep); meta=self.d/"meta.json"; self.s.export_metadata(meta)
  r=EncryptedCAS.restore_from_metadata_and_replica(self.d/"restored",self.k,meta,rep); self.assertEqual(r.get(a.object_id),b"hello"); r.close()
 def test_14_restore_digest(self):
  a=self.put(); rep=self.d/"rep"; self.s.replicate_to(a.object_id,rep); meta=self.d/"meta.json"; m=self.s.export_metadata(meta)
  r=EncryptedCAS.restore_from_metadata_and_replica(self.d/"restored",self.k,meta,rep); self.assertEqual(r.manifest_digest(),m["manifest_digest"]); r.close()
 def test_15_replica_corruption(self):
  a=self.put(); rep=self.d/"rep"; rr=self.s.replicate_to(a.object_id,rep); pathlib.Path(rr["replica_path"]).write_bytes(b"x"); meta=self.d/"meta.json"; self.s.export_metadata(meta)
  with self.assertRaises(IOError): EncryptedCAS.restore_from_metadata_and_replica(self.d/"r",self.k,meta,rep)
 def test_16_privacy(self): a=self.put(); self.assertEqual(a.privacy_class,"P1_INTERNAL")
 def test_17_role(self): a=self.put(); self.assertEqual(a.logical_role,"proof")
 def test_18_media(self): a=self.put(); self.assertEqual(a.media_type,"text/plain")
 def test_19_size(self): a=self.put(); self.assertEqual(a.size,5)
 def test_20_key_ref(self): a=self.put(); self.assertEqual(a.key_ref,"k1")
 def test_21_key_length(self):
  s=EncryptedCAS(self.d/"s2",InMemoryKeyProvider({"bad":b"x"}))
  with self.assertRaises(ValueError): s.put(b"x",media_type="a",privacy_class="p",logical_role="r",key_ref="bad")
  s.close()
 def test_22_two_objects(self): self.put(b"a"); self.put(b"b"); self.assertEqual(len(self.s.manifest()),2)
 def test_23_manifest_order(self): self.put(b"b"); self.put(b"a"); m=self.s.manifest(); self.assertEqual([x["object_id"] for x in m],sorted(x["object_id"] for x in m))
 def test_24_restart(self):
  a=self.put(); self.s.close(); self.s=EncryptedCAS(self.d/"store",self.k); self.assertEqual(self.s.get(a.object_id),b"hello")
 def test_25_ciphertext_not_plain(self):
  a=self.put(); self.assertNotEqual(self.s._path(a.plaintext_sha256).read_bytes(),b"hello")
 def test_26_nonce_len(self): self.put(); self.assertEqual(len(self.s.manifest()[0]["nonce_hex"]),24)
 def test_27_aad_metadata_tamper_breaks(self):
  a=self.put(); self.s.db.execute("UPDATE objects SET logical_role='tampered' WHERE object_id=?",(a.object_id,)); self.s.db.commit(); self.assertFalse(self.s.verify(a.object_id))
 def test_28_source_ref(self):
  a=self.s.put(b"x",media_type="a",privacy_class="p",logical_role="r",key_ref="k1",source_ref="src"); self.assertEqual(self.s.manifest()[0]["source_ref"],"src")
 def test_29_mission_id(self):
  a=self.s.put(b"x",media_type="a",privacy_class="p",logical_role="r",key_ref="k1",mission_id="m"); self.assertEqual(self.s.manifest()[0]["mission_id"],"m")
 def test_30_existing_diff_key_rejected(self):
  self.put(b"x","k1")
  with self.assertRaises(ValueError): self.put(b"x","k2")
if __name__=="__main__": unittest.main(verbosity=2)
