from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidenceops" / "ecertify_za" / "deployment" / "deploy_launch_now_cloud_run_canary.sh"
CONTRACT = ROOT / "evidenceops" / "ecertify_za" / "deployment" / "LAUNCH_NOW_CANARY_CONTRACT.json"


class ECertifyLaunchNowCanaryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_track_a_does_not_require_identity_provider_or_cloudsql(self) -> None:
        required = set(self.contract["required_runtime_inputs"])
        self.assertNotIn("ECERTIFY_IDP_PROVIDER", required)
        self.assertNotIn("ECERTIFY_DB_FACTORY", required)
        self.assertNotIn("ECERTIFY_CLOUDSQL_INSTANCE", required)
        self.assertNotIn("ECERTIFY_IDP_PROVIDER:-", self.script)
        self.assertNotIn("ECERTIFY_CLOUDSQL_INSTANCE:-", self.script)

    def test_integrity_signing_secret_is_required_without_reading_payload(self) -> None:
        self.assertIn("ECERTIFY_INTEGRITY_SIGNING_SECRET_NAME", self.script)
        self.assertIn("gcloud secrets describe", self.script)
        self.assertIn("ECERTIFY_INTEGRITY_SIGNING_KEY=", self.script)
        self.assertNotIn("gcloud secrets versions access", self.script)

    def test_canary_is_zero_traffic_and_authenticated(self) -> None:
        self.assertIn("--no-traffic", self.script)
        self.assertIn("--no-allow-unauthenticated", self.script)
        self.assertTrue(self.contract["provider_safety"]["zero_traffic"])
        self.assertFalse(self.contract["provider_safety"]["allow_unauthenticated"])

    def test_runtime_mode_is_explicitly_launch_now_production(self) -> None:
        self.assertIn("ECERTIFY_ENV=production", self.script)
        self.assertIn("ECERTIFY_MODE=launch_now", self.script)
        self.assertEqual("launch_now", self.contract["mode"])
        self.assertEqual("0.9.0", self.contract["acceptance"]["expected_version"])

    def test_health_contract_rejects_identity_provider_as_launch_dependency(self) -> None:
        self.assertIn('health.get("identity_provider_required_for_launch") is False', self.script)
        self.assertFalse(self.contract["acceptance"]["identity_provider_required_for_launch"])
        self.assertTrue(self.contract["acceptance"]["zero_possession_integrity_receipts"])

    def test_canary_runs_integrity_receipt_issue_and_verify_roundtrip(self) -> None:
        self.assertIn("/v1/integrity/receipt/issue", self.script)
        self.assertIn("/v1/integrity/receipt/verify", self.script)
        self.assertIn('result.get("valid") is True', self.script)
        self.assertTrue(self.contract["acceptance"]["receipt_roundtrip_valid"])

    def test_document_bytes_are_not_part_of_canary_payload(self) -> None:
        self.assertIn("document_sha256", self.script)
        self.assertIn("client_nonce", self.script)
        self.assertNotIn('"document_bytes"', self.script)
        self.assertFalse(self.contract["acceptance"]["document_bytes_transmitted"])

    def test_source_contract_never_self_certifies_public_launch(self) -> None:
        boundary = self.contract["maturity_boundary"]
        self.assertFalse(boundary["source_contract_proves_deployment"])
        self.assertFalse(boundary["successful_zero_traffic_canary_proves_public_launch"])
        self.assertFalse(self.contract["provider_safety"]["public_launch_authorised"])
        self.assertIn('"proof_scope": "zero-traffic provider canary only; not public production launch"', self.script)


if __name__ == "__main__":
    unittest.main()
