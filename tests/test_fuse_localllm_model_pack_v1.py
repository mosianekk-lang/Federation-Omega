from __future__ import annotations
import json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
PACK=ROOT/"products"/"fuse_localllm_modelpacks"/"qwen3_4b_q4_k_m"
class FuseLocalLLMModelPackTests(unittest.TestCase):
    def test_exact_model_contract(self):
        p=json.loads((PACK/"model_pack.json").read_text(encoding="utf-8"))
        self.assertEqual(p["model_revision"],"a9a60d009fa7ff9606305047c2bf77ac25dbec49")
        self.assertEqual(p["expected_size_bytes"],2497280256)
        self.assertEqual(p["sha256"],"7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5")
        self.assertEqual(p["license"],"Apache-2.0")
        self.assertTrue(p["commercial_distribution_allowed"])
        self.assertFalse(p["runtime_compatibility"]["verified_runtime_binding"])
    def test_provisioner_fails_closed_and_is_atomic(self):
        s=(PACK/"provision_model.ps1").read_text(encoding="utf-8")
        for token in ("Get-FileHash","MODEL_INTEGRITY_MISMATCH","MODEL_POST_MOVE_INTEGRITY_MISMATCH",".partial","Move-Item","2497280256","7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"):
            self.assertIn(token,s)
        self.assertIn("a9a60d009fa7ff9606305047c2bf77ac25dbec49",s)
    def test_no_model_presence_overclaim(self):
        p=json.loads((PACK/"model_pack.json").read_text(encoding="utf-8"))
        self.assertIn("MODEL_BYTES_IN_OWNER_CUSTODY",p["truth_boundary"])
        self.assertNotEqual(p["proof_state"],"MODEL_RUNTIME_VERIFIED")
if __name__=="__main__": unittest.main()
