from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "mobile" / "fuse-mobile" / "lab"
CONTRACT = ROOT / "governance" / "fuse_mobile_mdtaf_v1.json"
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-mdtaf-v1.yml"


class FuseMobileMdtafContractTests(unittest.TestCase):
    def test_permanent_contract_is_truth_bounded(self) -> None:
        data = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "FUSE-MOBILE-MDTAF-V1")
        self.assertEqual(data["authority_ceiling"], "A1_INTERNAL")
        self.assertFalse(data["external_effect_default"])
        self.assertTrue(data["truth_boundary"]["source_is_not_runtime"])
        self.assertTrue(data["truth_boundary"]["virtual_device_is_not_physical_device"])
        self.assertFalse(data["owner_reference_device"]["public_source_storage_allowed"])

    def test_owner_capture_is_privacy_minimised(self) -> None:
        source = (LAB / "capture_owner_device.py").read_text(encoding="utf-8").lower()
        forbidden_commands = [
            "pm list packages",
            "content query",
            "/sdcard",
            "dumpsys account",
            "dumpsys iphonesubinfo",
        ]
        for token in forbidden_commands:
            self.assertNotIn(token, source)
        self.assertIn('"personal_data_captured": false', source)
        self.assertIn('"hardware_unique_identifiers_captured": false', source)

    def test_certificate_refuses_missing_core_evidence(self) -> None:
        source = (LAB / "certify.py").read_text(encoding="utf-8")
        self.assertIn('verdict = "NOT_RELEASE_READY"', source)
        self.assertIn('"RELEASE_VERIFIED_WITH_DECLARED_LIMITATIONS"', source)
        self.assertIn('"physical_device_validation"', source)
        self.assertIn('"owasp_masvs_review"', source)

    def test_workflow_is_owner_dispatched_and_read_only(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read\n  issues: read", workflow)
        self.assertIn("github.event.issue.author_association == 'OWNER'", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("id-token: write", workflow)


if __name__ == "__main__":
    unittest.main()
