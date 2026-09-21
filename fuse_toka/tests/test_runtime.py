import tempfile,unittest
from pathlib import Path
from fuse_toka.catalog import OFFERINGS,RESTRICTED_CAPABILITIES
from fuse_toka.runtime import status,verify_download
class FuseTokaTests(unittest.TestCase):
    def test_catalog_has_commercial_surface(self): self.assertGreaterEqual(len(OFFERINGS),12); self.assertEqual(len({x["id"] for x in OFFERINGS}),len(OFFERINGS))
    def test_restricted_offensive_capabilities_are_explicit(self): self.assertIn("unauthorized_system_access",RESTRICTED_CAPABILITIES); self.assertIn("data_exfiltration",RESTRICTED_CAPABILITIES)
    def test_status_is_local_and_deterministic(self): self.assertEqual(status().app,"FUSE Toka"); self.assertTrue(status().version)
    def test_sha256_verification(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.bin"; p.write_bytes(b"abc"); self.assertTrue(verify_download(p,"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")); self.assertFalse(verify_download(p,"00"*32))
if __name__=="__main__": unittest.main()
