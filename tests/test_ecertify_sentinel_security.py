from __future__ import annotations

import unittest
from pathlib import Path

from evidenceops.ecertify_za.launch_now import LaunchNowEngine
from evidenceops.ecertify_za.security_controls import (
    deployment_contract_is_safe,
    launch_decision_is_truth_safe,
    tamper_is_rejected,
    threat_model_is_fully_gated,
)
from evidenceops.ecertify_za.zero_possession import ZeroPossessionReceiptService


DEPLOY = Path("evidenceops/ecertify_za/deployment/deploy_launch_now_cloud_run_canary.sh")
HTTP_APP = Path("evidenceops/ecertify_za/http_app.py")


class SentinelLaunchNowSecurityTests(unittest.TestCase):
    def test_threat_model_has_executable_gate_for_every_threat(self) -> None:
        self.assertTrue(threat_model_is_fully_gated())

    def test_signing_key_shorter_than_256_bits_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "INTEGRITY_SIGNING_KEY_TOO_SHORT"):
            ZeroPossessionReceiptService(b"short")

    def test_receipt_tamper_is_rejected(self) -> None:
        service = ZeroPossessionReceiptService(b"s" * 32)
        receipt = service.issue(document_sha256="a" * 64, client_nonce="sentinel-nonce-0001", now=1)
        self.assertTrue(tamper_is_rejected(service, receipt))

    def test_nonce_and_digest_inputs_are_bounded(self) -> None:
        service = ZeroPossessionReceiptService(b"s" * 32)
        with self.assertRaises(ValueError):
            service.issue(document_sha256="bad", client_nonce="sentinel-nonce-0001")
        with self.assertRaises(ValueError):
            service.issue(document_sha256="a" * 64, client_nonce="short")

    def test_zero_possession_http_lane_explicitly_rejects_document_byte_fields(self) -> None:
        source = HTTP_APP.read_text(encoding="utf-8")
        for field in ("document_bytes", "document_base64", "raw_document"):
            self.assertIn(field, source)
        self.assertIn("zero_possession_endpoint_rejects_document_bytes", source)

    def test_launch_labels_preserve_legal_and_identity_boundaries(self) -> None:
        engine = LaunchNowEngine()
        integrity = engine.route("copy")
        certified = engine.route("certified_copy")
        affidavit = engine.route("affidavit")
        self.assertTrue(launch_decision_is_truth_safe(integrity))
        self.assertTrue(launch_decision_is_truth_safe(certified))
        self.assertTrue(launch_decision_is_truth_safe(affidavit))
        self.assertTrue(integrity.launchable_without_idv_contract)
        self.assertTrue(certified.commissioner_required)
        self.assertTrue(affidavit.commissioner_required)

    def test_provider_canary_is_zero_traffic_and_secret_handle_only(self) -> None:
        script = DEPLOY.read_text(encoding="utf-8")
        self.assertTrue(deployment_contract_is_safe(script))

    def test_source_contract_never_authorises_public_launch(self) -> None:
        script = DEPLOY.read_text(encoding="utf-8")
        self.assertIn('"public_unauthenticated": False', script)
        self.assertIn('"traffic_promoted": False', script)
        self.assertIn("not public production launch", script)


if __name__ == "__main__":
    unittest.main()
