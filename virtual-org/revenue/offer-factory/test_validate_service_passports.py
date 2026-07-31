import json
import unittest
from pathlib import Path

from validate_service_passports import validate

class ServicePassportValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(Path(__file__).with_name("service-passports.json").read_text(encoding="utf-8"))

    def test_release_candidate_passes(self):
        self.assertEqual(validate(self.payload), [])

    def test_external_approval_cannot_be_disabled(self):
        changed = json.loads(json.dumps(self.payload))
        changed["external_approval_required"] = False
        self.assertTrue(any("external_approval_required" in error for error in validate(changed)))

    def test_duplicate_service_ids_fail(self):
        changed = json.loads(json.dumps(self.payload))
        changed["services"][1]["service_id"] = changed["services"][0]["service_id"]
        self.assertTrue(any("duplicated" in error for error in validate(changed)))

    def test_binding_price_is_rejected(self):
        changed = json.loads(json.dumps(self.payload))
        changed["services"][0]["pricing_band_zar"]["status"] = "APPROVED"
        self.assertTrue(any("INTERNAL_NONBINDING" in error for error in validate(changed)))

if __name__ == "__main__":
    unittest.main()
