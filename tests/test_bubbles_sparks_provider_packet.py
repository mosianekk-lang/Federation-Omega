from __future__ import annotations

import unittest
from pathlib import Path

from bubbles.sparks_provider_packet import SparksProviderPacket


ROOT = Path(__file__).resolve().parents[1]


class SparksProviderPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.packet = SparksProviderPacket.load()

    def test_packet_binds_exact_current_main_and_two_flagships(self) -> None:
        self.assertEqual("d35a4c3047896f06a82f8de7365034a73ff1bc66", self.packet.source_sha)
        self.assertEqual({"CIOS", "ECERTIFY"}, set(self.packet.projects))
        self.assertEqual("BLOCKED_EXTERNAL_PACKET_READY", self.packet.payload["execution_state"])
        self.assertFalse(self.packet.payload["authorized_execution_surface"])

    def test_all_bound_source_files_exist(self) -> None:
        result = self.packet.verify_source_tree(ROOT)
        self.assertTrue(result["source_files_present"], result)
        self.assertEqual([], result["missing_source_files"])

    def test_without_authorised_surface_execution_fails_closed(self) -> None:
        result = self.packet.assess_authority(authorized_execution_surface=False)
        self.assertFalse(result["execution_allowed"])
        self.assertEqual("BLOCKED_EXTERNAL_PACKET_READY", result["state"])

    def test_authority_without_provider_identity_readback_still_fails_closed(self) -> None:
        result = self.packet.assess_authority(authorized_execution_surface=True)
        self.assertFalse(result["execution_allowed"])
        self.assertEqual("PROVIDER_IDENTITY_READBACK_REQUIRED", result["reason"])

    def test_authority_plus_identity_readback_makes_canary_ready_not_verified(self) -> None:
        result = self.packet.assess_authority(
            authorized_execution_surface=True,
            provider_identity_readback="provider://identity/runtime-service-account",
        )
        self.assertTrue(result["execution_allowed"])
        self.assertEqual("AUTHORISED_CANARY_EXECUTION_READY", result["state"])

    def test_cios_receipt_requires_exact_source_and_all_semantics(self) -> None:
        receipt = {
            "provider_project": "project",
            "provider_service_identity": "service-account",
            "provider_revision": "rev-1",
            "image_digest": "sha256:abc",
            "source_sha": self.packet.source_sha,
            "health_semantics_verified": True,
            "readiness_semantics_verified": True,
            "persistence_verified": True,
            "audit_chain_verified": True,
            "rollback_verified": True,
            "external_effects_enabled": False,
        }
        result = self.packet.assess_receipt("CIOS", receipt)
        self.assertTrue(result["provider_verified"])
        drift = dict(receipt)
        drift["source_sha"] = "0" * 40
        self.assertFalse(self.packet.assess_receipt("CIOS", drift)["provider_verified"])

    def test_ecertify_receipt_fails_if_public_or_document_bytes_cross_boundary(self) -> None:
        receipt = {
            "provider_project": "project",
            "runtime_service_account": "service-account",
            "provider_revision": "rev-1",
            "image_digest": "sha256:def",
            "source_sha": self.packet.source_sha,
            "semantic_health_verified": True,
            "receipt_roundtrip_verified": True,
            "document_bytes_transmitted": False,
            "traffic_promoted": False,
            "public_unauthenticated": False,
            "rollback_verified": True,
        }
        self.assertTrue(self.packet.assess_receipt("ECERTIFY", receipt)["provider_verified"])
        unsafe = dict(receipt)
        unsafe["public_unauthenticated"] = True
        unsafe["document_bytes_transmitted"] = True
        result = self.packet.assess_receipt("ECERTIFY", unsafe)
        self.assertFalse(result["provider_verified"])
        self.assertIn("ACCEPTANCE_FAILED:public_unauthenticated", result["failures"])
        self.assertIn("ACCEPTANCE_FAILED:document_bytes_transmitted", result["failures"])

    def test_packet_contains_no_raw_secret_value_fields(self) -> None:
        text = (ROOT / "bubbles" / "sparks_provider_execution_packet.json").read_text(encoding="utf-8").casefold()
        for forbidden in ('"secret_value"', '"token_value"', '"credential_value"', '"private_key"', '"password"'):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
