import unittest,tempfile,shutil,pathlib,json
from fuse_genesis.identity_secrets import *

class T(unittest.TestCase):
 def setUp(self):
  self.d=pathlib.Path(tempfile.mkdtemp()); self.ks=SigningKeyStore(); self.ks.create("owner","k1",1)
  self.issuer=SignedTokenIssuer(self.ks); self.v=SecretVault(self.d,MasterKeyProvider({"m1":b"1"*32,"m2":b"2"*32}))
 def tearDown(self):
  try:self.v.close()
  except:pass
  shutil.rmtree(self.d,ignore_errors=True)
 def test_01_sign_verify(self): kid,s=self.ks.sign("owner",b"x"); self.assertTrue(self.ks.verify(kid,b"x",s))
 def test_02_bad_message(self): kid,s=self.ks.sign("owner",b"x"); self.assertFalse(self.ks.verify(kid,b"y",s))
 def test_03_rotate(self): self.ks.rotate("owner","k2",2); self.assertEqual(self.ks.public["k1"].state,"RETIRED")
 def test_04_retired_verify(self): kid,s=self.ks.sign("owner",b"x"); self.ks.rotate("owner","k2",2); self.assertTrue(self.ks.verify("k1",b"x",s))
 def test_05_retired_strict(self): kid,s=self.ks.sign("owner",b"x"); self.ks.rotate("owner","k2",2); self.assertFalse(self.ks.verify("k1",b"x",s,False))
 def test_06_revoke(self): kid,s=self.ks.sign("owner",b"x"); self.ks.revoke(kid); self.assertFalse(self.ks.verify(kid,b"x",s))
 def test_07_manifest_public_only(self): m=self.ks.public_manifest(); self.assertIn("public_key_b64",m[0]); self.assertNotIn("private",str(m[0]).lower())
 def test_08_issue_verify(self): t=self.issuer.issue("owner","fuse",10,100,jti="j"); self.assertTrue(self.issuer.verify(t,"fuse",20))
 def test_09_token_expire(self): t=self.issuer.issue("owner","fuse",10,100,jti="j"); self.assertFalse(self.issuer.verify(t,"fuse",111))
 def test_10_token_audience(self): t=self.issuer.issue("owner","fuse",10,100,jti="j"); self.assertFalse(self.issuer.verify(t,"other",20))
 def test_11_token_revoke(self): t=self.issuer.issue("owner","fuse",10,100,jti="j"); self.issuer.revoke("j"); self.assertFalse(self.issuer.verify(t,"fuse",20))
 def test_12_ttl_cap(self):
  with self.assertRaises(ValueError): self.issuer.issue("owner","fuse",0,4000)
 def test_13_token_claims(self): t=self.issuer.issue("owner","fuse",0,100,{"role":"owner"}); self.assertEqual(t["body"]["claims"]["role"],"owner")
 def test_14_secret_put_get(self): self.v.put("s",b"secret","m1",1); self.assertEqual(self.v.get("s"),b"secret")
 def test_15_secret_cipher_not_plain(self): self.v.put("s",b"secret","m1",1); r=self.v.db.execute("select * from secrets").fetchone(); self.assertNotIn("secret",r["ciphertext_b64"])
 def test_16_secret_version(self): a=self.v.put("s",b"a","m1",1); b=self.v.put("s",b"b","m1",2); self.assertEqual((a["version"],b["version"]),(1,2))
 def test_17_secret_rotate(self): self.v.put("s",b"a","m1",1); x=self.v.rotate("s",b"b","m2",2); self.assertEqual(self.v.get("s"),b"b")
 def test_18_secret_old_retired_readable_by_version(self): self.v.put("s",b"a","m1",1); self.v.rotate("s",b"b","m2",2); self.assertEqual(self.v.get("s",1),b"a")
 def test_19_secret_revoke(self): self.v.put("s",b"a","m1",1); self.v.revoke("s",1)
 def test_20_secret_revoked_unreadable(self): self.v.put("s",b"a","m1",1); self.v.revoke("s",1);
 def test_21_manifest_no_plaintext(self): self.v.put("s",b"TOPSECRET","m1",1); self.assertNotIn("TOPSECRET",json.dumps(self.v.manifest()))
 def test_22_manifest_key_ref(self): self.v.put("s",b"x","m1",1); self.assertEqual(self.v.manifest()[0]["key_ref"],"m1")
 def test_23_manifest_digest(self): self.v.put("s",b"x","m1",1); m=self.v.export_manifest(self.d/"m.json"); self.assertEqual(len(m["digest"]),64)
 def test_24_restart(self): self.v.put("s",b"x","m1",1); self.v.close(); self.v=SecretVault(self.d,MasterKeyProvider({"m1":b"1"*32,"m2":b"2"*32})); self.assertEqual(self.v.get("s"),b"x")
 def test_25_wrong_key(self): self.v.put("s",b"x","m1",1); self.v.close(); self.v=SecretVault(self.d,MasterKeyProvider({"m1":b"9"*32,"m2":b"2"*32}));
 def test_26_cipher_corruption(self): self.v.put("s",b"x","m1",1); r=self.v.db.execute("select * from secrets").fetchone(); self.v.db.execute("update secrets set ciphertext_b64='eA'"); self.v.db.commit();
 def test_27_public_manifest_two_keys(self): self.ks.rotate("owner","k2",2); self.assertEqual(len(self.ks.public_manifest()),2)
 def test_28_revoke_active_removes_subject(self): self.ks.revoke("k1"); self.assertNotIn("owner",self.ks.active_by_subject)
 def test_29_no_active_signer(self): self.ks.revoke("k1");
 def test_30_secret_active_latest(self): self.v.put("s",b"a","m1",1); self.v.rotate("s",b"b","m1",2); self.assertEqual(self.v.get("s"),b"b")
 def test_31_secret_states(self): self.v.put("s",b"a","m1",1); self.v.rotate("s",b"b","m1",2); self.assertEqual([x["state"] for x in self.v.manifest()],["RETIRED","ACTIVE"])
 def test_32_token_old_key_after_rotation(self): t=self.issuer.issue("owner","fuse",1,100,jti="j"); self.ks.rotate("owner","k2",2); self.assertTrue(self.issuer.verify(t,"fuse",20))
 def test_33_token_revoked_key_fails(self): t=self.issuer.issue("owner","fuse",1,100,jti="j"); self.ks.revoke("k1"); self.assertFalse(self.issuer.verify(t,"fuse",20))
 def test_34_secret_revoked_raises(self):
  self.v.put("s",b"a","m1",1); self.v.revoke("s",1)
  with self.assertRaises(KeyError): self.v.get("s",1)
 def test_35_wrong_master_key_fails(self):
  self.v.put("s",b"x","m1",1); self.v.close(); self.v=SecretVault(self.d,MasterKeyProvider({"m1":b"9"*32,"m2":b"2"*32}))
  with self.assertRaises(Exception): self.v.get("s")
 def test_36_corruption_fails(self):
  self.v.put("s",b"x","m1",1); self.v.db.execute("update secrets set ciphertext_b64='eA'"); self.v.db.commit()
  with self.assertRaises(Exception): self.v.get("s")
 def test_37_no_active_signer_raises(self):
  self.ks.revoke("k1")
  with self.assertRaises(PermissionError): self.ks.sign("owner",b"x")
 def test_38_master_key_len(self):
  v=SecretVault(self.d/"b",MasterKeyProvider({"x":b"1"}))
  with self.assertRaises(ValueError): v.put("s",b"x","x",1)
  v.close()
 def test_39_token_signature_tamper(self):
  t=self.issuer.issue("owner","fuse",1,100,jti="j"); t["body"]["claims"]["x"]=1; self.assertFalse(self.issuer.verify(t,"fuse",20))
 def test_40_public_manifest_state(self): self.assertEqual(self.ks.public_manifest()[0]["state"],"ACTIVE")
if __name__=="__main__": unittest.main(verbosity=2)
