from __future__ import annotations
import hashlib, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/"products"/"fuse_localllm_desktop"/"v0.2.2"/"upstream"
CONTRACT=ROOT/"governance"/"fuse_localllm_desktop_v1.json"
CUSTODY=ROOT/"products"/"fuse_localllm_desktop"/"v0.2.2"/"DRIVE_CUSTODY.json"
class FuseLocalLLMDesktopSourceTests(unittest.TestCase):
    def test_drive_source_manifest_exact_bytes(self):
        b=(SRC/"SOURCE_MANIFEST.json").read_bytes()
        self.assertEqual(hashlib.sha256(b).hexdigest(),"723a7cf4c3e8f87425884a0e8b8a077740e73b99d4d5875073f689d0ace45ffb")
        manifest=json.loads(b); excluded={"tests/__pycache__/test_product.cpython-313.pyc"}; checked=0
        for rel,meta in manifest.items():
            if rel in excluded: continue
            p=SRC/rel; self.assertTrue(p.is_file(),rel)
            self.assertEqual(p.stat().st_size,int(meta["bytes"]),rel)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),meta["sha256"],rel); checked+=1
        self.assertEqual(checked,21)
    def test_custody_and_product_contract(self):
        custody=json.loads(CUSTODY.read_text(encoding="utf-8")); contract=json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(custody["source_drive_folder_id"],"1sPpaA8G4ZkEy-4WkC_Ph81QOs4fiYj61")
        self.assertEqual(custody["source_file_count"],21); self.assertTrue(custody["all_non_generated_manifest_hashes_verified"])
        self.assertEqual(contract["product_version"],"0.2.2"); self.assertEqual(contract["current_maturity"],"DRIVE_SOURCE_BYTE_CUSTODY_VERIFIED")
    def test_pinned_llama_and_product_binaries(self):
        cmake=(SRC/"CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("60081bb2b5b3294165a4d67c5cbeebe74c868014",cmake)
        self.assertIn("project(FUSE_LocalLLM_Desktop VERSION 0.2.2",cmake)
        self.assertIn("add_executable(FUSE-LocalLLM ",cmake); self.assertIn("add_executable(FUSE-LocalLLM-Desktop WIN32",cmake)
    def test_product_source_court(self):
        ui=(SRC/"ui"/"index.html").read_text(encoding="utf-8"); app=(SRC/"ui"/"app.js").read_text(encoding="utf-8")
        main=(SRC/"src"/"main.cpp").read_text(encoding="utf-8"); launcher=(SRC/"src"/"desktop_launcher.cpp").read_text(encoding="utf-8")
        for token in ("view-chat","view-models","view-library","view-apps","view-settings"): self.assertIn(token,ui)
        self.assertIn("/v1/chat/completions",app); self.assertIn("GET /healthz",main); self.assertIn('"version":"0.2.2"',main)
        self.assertIn("CREATE_NO_WINDOW",launcher); self.assertIn("msedge.exe",launcher)
if __name__=="__main__": unittest.main()
