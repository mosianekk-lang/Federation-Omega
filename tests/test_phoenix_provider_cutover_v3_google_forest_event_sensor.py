import json
from pathlib import Path
import unittest

from ops.apps_script_authorization_gate import validate_apps_script_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations" / "google_workspace" / "forest_event_sensor.gs"
MANIFEST = ROOT / "integrations" / "google_workspace" / "forest_event_sensor.appsscript.json"
CONTRACT = ROOT / "governance" / "google_forest_event_sensor_v1.json"


class GoogleForestEventSensorContractTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text(encoding="utf-8")
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_trigger_only_source_passes_apps_script_authorization_gate(self):
        self.assertEqual(self.source, validate_apps_script_source(self.source))
        self.assertNotIn("function doPost", self.source)
        self.assertNotIn("function doGet", self.source)
        self.assertNotIn('"webapp"', MANIFEST.read_text(encoding="utf-8"))

    def test_source_uses_metadata_only_provider_scopes(self):
        scopes = set(self.manifest["oauthScopes"])
        self.assertIn("https://www.googleapis.com/auth/gmail.readonly", scopes)
        self.assertIn("https://www.googleapis.com/auth/drive.metadata.readonly", scopes)
        self.assertNotIn("https://mail.google.com/", scopes)
        self.assertNotIn("https://www.googleapis.com/auth/drive", scopes)

    def test_source_never_exports_subject_body_or_drive_content(self):
        lowered = self.source.lower()
        self.assertNotIn("getsubject(", lowered)
        self.assertNotIn("getbody(", lowered)
        self.assertNotIn("getplainbody(", lowered)
        self.assertNotIn("alt=media", lowered)
        self.assertIn("private_content_included: false", lowered)

    def test_dispatch_is_disabled_by_default_and_secret_value_not_persisted(self):
        self.assertTrue(self.contract["cost_posture"]["dispatch_disabled_by_default"])
        self.assertFalse(self.contract["dispatch_binding"]["secret_value_in_source"])
        self.assertFalse(self.contract["dispatch_binding"]["secret_value_in_script_properties"])
        self.assertIn("FFO_SENSOR_GITHUB_TOKEN_SECRET_RESOURCE", self.source)
        self.assertNotIn("ghp_", self.source)
        self.assertNotIn("github_pat_", self.source)

    def test_c0_target_does_not_claim_zero_bill_or_deployment(self):
        self.assertEqual("C0_INCLUDED_FREE", self.contract["cost_posture"]["target_class"])
        self.assertTrue(self.contract["cost_posture"]["secret_manager_incremental_cost_must_be_verified_before_dispatch_enable"])
        self.assertFalse(self.contract["truth_boundary"]["apps_script_quota_proves_zero_bill"])
        self.assertFalse(self.contract["truth_boundary"]["source_candidate_proves_deployment"])
        self.assertFalse(self.contract["truth_boundary"]["end_to_end_event_delivery_verified"])

    def test_public_contract_contains_no_exact_legacy_provider_pointer(self):
        text = CONTRACT.read_text(encoding="utf-8")
        self.assertNotIn("archived_script_id", text)
        self.assertTrue(self.contract["privacy_contract"]["private_exact_provider_pointers_in_public_source"] is False)

    def test_sensor_cadence_is_bounded_and_queue_first(self):
        self.assertIn("everyMinutes(15)", self.source)
        self.assertIn("FFO_SENSOR_QUEUE_(config, event, 'PENDING')", self.source)
        self.assertIn("if (config.dispatchEnabled)", self.source)


if __name__ == "__main__":
    unittest.main()
