from __future__ import annotations
import importlib,json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class AegisOmegaUnifiedContractTests(unittest.TestCase):
    def test_edge_client_is_owner_triggered_and_minimized(self):
        check=(ROOT/'mobile/fuse-mobile/src/aegisSecurityCheck.ts').read_text(); card=(ROOT/'mobile/fuse-mobile/src/AegisSecurityCheckCard.tsx').read_text()
        for forbidden in ('setInterval(','BackgroundFetch','TaskManager','AccessibilityService','startLocationUpdates','contacts','installed_apps','app_list'): self.assertNotIn(forbidden,check)
        self.assertIn('runOwnerTriggeredAegisSecurityCheck',check); self.assertIn('Run AEGIS security check',card); self.assertIn('No background monitoring',card); self.assertIn('provider_state_verified',check); self.assertIn('case_id?: string | null',check)
    def test_gateway_requires_fuse_session_and_private_server_identity(self):
        adapter=(ROOT/'services/fuse_mobile_gateway/aegis_edge_adapter.py').read_text(); bridge=(ROOT/'services/fuse_mobile_gateway/aegis_edge_bridge.py').read_text(); self.assertIn('runtime.verify_session',adapter); self.assertIn('FUSE_AEGIS_PRIVATE_URL',adapter); self.assertIn('fetch_id_token',adapter); self.assertIn('evidence_chain_valid',adapter); self.assertIn('provider_effect_performed',adapter); self.assertIn('case_id',bridge)
        for secret in ('GEMINI_API_KEY','OPENAI_API_KEY','AEGIS_HMAC_SECRET'): self.assertNotIn(secret,adapter); self.assertNotIn(secret,bridge)
    def test_gateway_adapter_imports_through_real_package_path(self):
        module=importlib.import_module('services.fuse_mobile_gateway.aegis_edge_adapter'); self.assertTrue(callable(module.build_aegis_edge_router)); self.assertEqual(module.EdgeBridgeError.__module__,'services.fuse_mobile_gateway.aegis_edge_bridge')
    def test_android_native_module_is_bounded_posture_only(self):
        native=(ROOT/'mobile/fuse-mobile/modules/aegis-edge-posture/android/src/main/java/expo/modules/aegisedgeposture/AegisEdgePostureModule.kt').read_text(); self.assertIn('SECURITY_PATCH',native); self.assertIn('isDeviceSecure',native); self.assertIn('FLAG_DEBUGGABLE',native)
        for forbidden in ('READ_SMS','READ_CONTACTS','ACCESS_FINE_LOCATION','QUERY_ALL_PACKAGES','VpnService','AccessibilityService'): self.assertNotIn(forbidden,native)
    def test_edge_core_guards_strict_index_access(self):
        core=(ROOT/'mobile/fuse-mobile/src/aegisEdgeCore.ts').read_text()
        self.assertIn("const major = match?.[1];",core)
        self.assertIn("return major ?? text.slice(0, 16);",core)
        self.assertIn("if (!yearText || !monText) return null;",core)
        self.assertNotIn("return match ? match[1] : text.slice(0, 16);",core)
        self.assertNotIn("const [year, mon] = month.split('-').map(Number);",core)
    def test_backend_stays_defensive_and_auto_promotion_is_false(self):
        api=(ROOT/'services/aegis_omega/src/aegis_omega/api.py').read_text(); policy=(ROOT/'services/aegis_omega/src/aegis_omega/policy.py').read_text(); self.assertIn('defensive-only',api); self.assertIn('automatic_model_promotion',api); self.assertIn('high_impact_response_requires_human_approval',api); self.assertRegex(policy,re.compile(r'approval_required'))
    def test_proofos_extension_maps_source_core_and_defers_provider_epoch(self):
        ext=json.loads((ROOT/'governance/proofos_omega_policy_extension_aegis_omega_v1.json').read_text()); flat=json.dumps(ext,sort_keys=True)
        for marker in ('services/aegis_omega/**','mobile/fuse-mobile/modules/aegis-edge-posture/**','services/fuse_mobile_gateway/aegis_edge_*.py','mobile/fuse-mobile/app/index.tsx','services/fuse_mobile_gateway/app.py'): self.assertIn(marker,flat)
        self.assertIn('AEGIS_OMEGA',flat); self.assertIn('AEGIS_EDGE',flat)
        self.assertNotIn('aegis_omega_provider_workflow',flat)
        self.assertNotIn('.github/workflows/aegis-omega-zero-traffic-v1.yml',flat)
if __name__=='__main__': unittest.main()
