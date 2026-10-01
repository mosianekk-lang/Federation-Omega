from __future__ import annotations
import json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
OVER=ROOT/"products"/"fuse_localllm_desktop"/"v0.3.0"
CONTRACT=ROOT/"governance"/"fuse_localllm_gemini_provider_v1.json"

class FuseLocalLLMGeminiProviderTests(unittest.TestCase):
    def test_contract_and_roles(self):
        c=json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(c["product_overlay_version"],"0.3.0")
        self.assertEqual(c["primary_orchestrator"],"SOVARA")
        self.assertFalse(c["proof"]["matched_2x_performance_verified"])
        roles=json.loads((OVER/"gemini_roles.json").read_text(encoding="utf-8"))
        self.assertEqual(len(roles["roles"]),8)
        self.assertEqual(roles["model"],"gemini-2.5-flash")
    def test_provider_fabric_hard_boundaries(self):
        s=(OVER/"FUSE-LocalLLM-ProviderFabric.ps1").read_text(encoding="utf-8")
        for token in ("GOOGLE_VERTEX_AI","FUSE_LOCAL_LLM","CLOUD_DENIED_DATA_CLASSIFICATION",
                      "GCLOUD_ADC_ACCESS_TOKEN","NO_ORACLE_NO_WINNER","global_provider_promotion=$false",
                      "CONFIDENTIAL","LEGAL_EVIDENCE","SECRET"):
            self.assertIn(token,s)
        self.assertNotIn("gemini.key",s.lower())
        self.assertNotIn("api_key",s.lower())
    def test_verified_role_mechanisms_present(self):
        s=(OVER/"FUSE-LocalLLM-ProviderFabric.ps1").read_text(encoding="utf-8")
        for role in ("ALPHA_OMEGA_REASONER","CFBE_CRITIC","CREATIVE_BRIEF_COMPILER","DESIGNIR_VALIDATOR",
                     "ROUTE_RANKER","STORYBOARD_CONTINUITY_CRITIC","PROVENANCE_ANALYST","CHALLENGER_JUDGE"):
            self.assertIn(role,s)
        self.assertIn("Get-DerivedMetrics",s)
        self.assertIn("quality_regression",s)
        self.assertIn("criterion_regressions",s)
    def test_installers_are_current_user_only(self):
        install=(OVER/"install_hybrid_current_user.ps1").read_text(encoding="utf-8")
        uninstall=(OVER/"uninstall_hybrid_current_user.ps1").read_text(encoding="utf-8")
        self.assertIn("LOCALAPPDATA",install)
        self.assertIn("provider-fabric",install)
        self.assertIn("install_core_current_user.ps1",install)
        self.assertIn("uninstall_core_current_user.ps1",uninstall)
        self.assertNotIn("HKLM",install+uninstall)
    def test_windows_package_recursively_attests_overlay(self):
        workflow=(ROOT/".github"/"workflows"/"fuse-localllm-desktop-windows-build-v1.yml").read_text(encoding="utf-8")
        self.assertIn("Get-ChildItem $releaseRoot -Recurse -File", workflow)
        self.assertIn("provider-fabric/FUSE-LocalLLM-ProviderFabric.ps1", workflow)
        self.assertIn("provider-fabric/gemini_roles.json", workflow)
        self.assertIn("provider_fabric_sha256", workflow)
        self.assertIn("gemini_roles_sha256", workflow)
        self.assertIn("checksum_manifest_sha256", workflow)

    def test_v022_custody_baseline_not_replaced(self):
        self.assertTrue((ROOT/"products"/"fuse_localllm_desktop"/"v0.2.2"/"upstream"/"SOURCE_MANIFEST.json").is_file())
        self.assertTrue((OVER/"README.md").is_file())

if __name__=="__main__":
    unittest.main()
