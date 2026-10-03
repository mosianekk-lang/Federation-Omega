import base64,hashlib,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fuse_toka import runtime
from fuse_toka.catalog import OFFERINGS,RESTRICTED_CAPABILITIES
from fuse_toka.runtime import RuntimeStatus,canonical_update_payload,status,verify_download,verify_update_manifest


class FuseTokaTests(unittest.TestCase):
    def setUp(self):
        self.now=int(time.time())
        self.private=Ed25519PrivateKey.generate()
        public=self.private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.public_b64=base64.b64encode(public).decode()
        self.root_id=hashlib.sha256(public).hexdigest()
        self.st=RuntimeStatus("FUSE Toka","0.1.1","Windows","AMD64",True,"stable","x")

    def manifest(self,**overrides):
        m={"version":"0.1.1","url":"https://updates.example/fuse-toka-0.1.1.exe","sha256":"ab"*32,"root_id":self.root_id,"channel":"stable","issued_at_epoch":self.now-10,"expires_at_epoch":self.now+3600}
        m.update(overrides)
        m["signature"]=base64.b64encode(self.private.sign(canonical_update_payload(m))).decode()
        return m

    def env(self):
        return {"FUSE_TOKA_TRUST_ROOT_ID":self.root_id,"FUSE_TOKA_TRUST_ROOT_ED25519_PUBLIC_KEY_B64":self.public_b64}

    def test_catalog_has_commercial_surface(self):
        self.assertGreaterEqual(len(OFFERINGS),12)
        self.assertEqual(len({x["id"] for x in OFFERINGS}),len(OFFERINGS))

    def test_restricted_offensive_capabilities_are_explicit(self):
        self.assertIn("unauthorized_system_access",RESTRICTED_CAPABILITIES)
        self.assertIn("data_exfiltration",RESTRICTED_CAPABILITIES)

    def test_status_is_local_and_deterministic(self):
        self.assertEqual(status().app,"FUSE Toka")
        self.assertTrue(status().version)

    def test_valid_ed25519_signature_is_verified_but_not_auto_applied(self):
        with patch.dict(os.environ,self.env(),clear=False):
            self.assertEqual((True,"UPDATE_MANIFEST_SIGNATURE_VERIFIED"),verify_update_manifest(self.manifest(),self.st,self.now))

    def test_tampered_manifest_is_rejected(self):
        m=self.manifest(); m["version"]="9.9.9"
        with patch.dict(os.environ,self.env(),clear=False):
            self.assertEqual((False,"UPDATE_REJECTED_INVALID_SIGNATURE"),verify_update_manifest(m,self.st,self.now))

    def test_unsafe_update_url_is_rejected_even_when_signed(self):
        m=self.manifest(url="http://updates.example/fuse.exe")
        with patch.dict(os.environ,self.env(),clear=False):
            self.assertEqual((False,"UPDATE_REJECTED_UNSAFE_URL"),verify_update_manifest(m,self.st,self.now))

    def test_missing_public_key_fails_closed(self):
        with patch.dict(os.environ,{"FUSE_TOKA_TRUST_ROOT_ID":"","FUSE_TOKA_TRUST_ROOT_ED25519_PUBLIC_KEY_B64":""},clear=False):
            self.assertEqual((False,"UPDATE_HELD_TRUST_ROOT_KEY_UNAVAILABLE"),verify_update_manifest(self.manifest(),self.st,self.now))

    def test_expired_and_wrong_channel_manifests_are_held(self):
        with patch.dict(os.environ,self.env(),clear=False):
            self.assertEqual((False,"UPDATE_REJECTED_EXPIRED_OR_FUTURE_MANIFEST"),verify_update_manifest(self.manifest(expires_at_epoch=self.now-1),self.st,self.now))
            self.assertEqual((False,"UPDATE_HELD_CHANNEL_MISMATCH"),verify_update_manifest(self.manifest(channel="beta"),self.st,self.now))

    def test_sha256_verification(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.bin"; p.write_bytes(b"abc")
            self.assertTrue(verify_download(p,"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"))
            self.assertFalse(verify_download(p,"00"*32))

    def test_signed_update_state_never_auto_applies(self):
        m=self.manifest()
        hb={"state":"CONNECTED","runtime":{},"server":{"update":m}}
        with patch.dict(os.environ,self.env(),clear=False),patch.object(runtime,"heartbeat",return_value=hb):
            result=runtime.signed_update_state()
        self.assertEqual("UPDATE_MANIFEST_SIGNATURE_VERIFIED_DOWNLOAD_NOT_AUTO_APPLIED",result["state"])
        self.assertNotIn("signature",result["candidate"])


if __name__=="__main__":
    unittest.main()
