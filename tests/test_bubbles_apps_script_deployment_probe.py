from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bubbles.apps_script_deployment_probe import (
    ARCHON_SCRIPT_DEPLOYMENT_ID,
    ARCHON_SCRIPT_URL,
    augment_receipt,
    run_probe,
)


class AppsScriptDeploymentProbeTests(unittest.TestCase):
    def test_exact_deployment_id_and_exec_url_are_bound(self) -> None:
        self.assertEqual(
            "AKfycbyaxovYOyaoMWFdsAZnbl2AIFU0PFY3hcGF-QRM1dmDqdtEHRFI7Ud7L_p7YCCVMG3J",
            ARCHON_SCRIPT_DEPLOYMENT_ID,
        )
        self.assertEqual(
            f"https://script.google.com/macros/s/{ARCHON_SCRIPT_DEPLOYMENT_ID}/exec",
            ARCHON_SCRIPT_URL,
        )

    def test_health_semantics_can_be_verified_without_mutation(self) -> None:
        def fake_http(url: str, *, follow_redirects: bool, timeout: int = 25):
            if "action=health_check" in url and follow_redirects:
                return {"http_status": 200, "body": {"ok": True, "action": "health_check"}, "final_url": url}
            if "action=openapi" in url and follow_redirects:
                return {"http_status": 200, "body": {"text": "openapi: 3.1.0"}, "final_url": url}
            return {"http_status": 302, "body": {"text": ""}, "location": "https://script.googleusercontent.com/", "final_url": url}

        with patch("bubbles.apps_script_deployment_probe._http", side_effect=fake_http):
            receipt = run_probe()
        self.assertEqual("DEPLOYMENT_HEALTH_SEMANTICS_VERIFIED", receipt["overall_classification"])
        self.assertFalse(receipt["mutation_attempted"])
        self.assertFalse(receipt["credential_values_recorded"])

    def test_augment_receipt_preserves_existing_provider_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            path.write_text(json.dumps({"schema": "EXISTING", "surfaces": {"x": {"ok": True}}}), encoding="utf-8")
            with patch(
                "bubbles.apps_script_deployment_probe.run_probe",
                return_value={"overall_classification": "DEPLOYMENT_PROVIDER_REACHABLE_ACTION_SEMANTICS_UNVERIFIED"},
            ):
                receipt = augment_receipt(path)
            self.assertEqual("EXISTING", receipt["schema"])
            self.assertTrue(receipt["surfaces"]["x"]["ok"])
            self.assertIn("archon_apps_script_exact_deployment", receipt["surface_corrections"])


if __name__ == "__main__":
    unittest.main()
