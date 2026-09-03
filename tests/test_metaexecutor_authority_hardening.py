from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'apps_script/architron_hardening/MetaExecutor_v2_1.gs').read_text()
G=json.loads((ROOT/'governance/metaexecutor_v2_1_hardening.json').read_text())
class TestHardenedMetaExecutor(unittest.TestCase):
    def test_a0_a1_mode(self): self.assertIn("authorityMode: 'A0_A1_ONLY'",S)
    def test_no_recurring_trigger_install(self): self.assertNotIn("ScriptApp.newTrigger(META_V2.triggerHandler)",S)
    def test_no_automatic_email(self): self.assertNotIn("GmailApp.sendEmail",S); self.assertNotIn("MailApp.sendEmail",S)
    def test_reusable_marker_rejected(self): self.assertIn("LEGACY_REUSABLE_APPROVAL_MARKER_REJECTED",S)
    def test_effect_inheritance(self): self.assertIn("intrinsicFunctionRiskV21_",S); self.assertIn("HELD_AUTHORITY_ACTION_SPECIFIC_EXECUTOR_REQUIRED",S)
    def test_high_actions_disabled(self):
        for a in ["SEND_STATUS_EMAIL","SNAPSHOT_PROJECT","UPSERT_SCRIPT_FILE","INSTALL_MODULE","ROLLBACK_PROJECT"]: self.assertRegex(S,rf"\['{a}', false")
    def test_nested_connector_held(self):
        for fn in ["runFederationConnectorKernelV5","registerFederationSourceV5","runArchitronCloudConnector"]: self.assertIn(fn,S)
    def test_manifest(self): self.assertEqual(G["authority_mode"],"A0_A1_ONLY"); self.assertFalse(G["reusable_approval_marker_authoritative"]); self.assertFalse(G["outbound_email"])
if __name__=='__main__': unittest.main()
