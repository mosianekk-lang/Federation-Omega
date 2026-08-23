from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "attachment_lineage",
    ROOT / "federation_consolidation/provider_authority_attachment.py",
)
attachment = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = attachment
spec.loader.exec_module(attachment)


BASE = dict(
    target_project_id="sov-hybrid-suite",
    target_project_number="257649435135",
    oauth_consumer_project_number="516690968552",
    transport_project_number="516699068552",
)


class GoogleIdentityLineageGuardTests(unittest.TestCase):
    def classify(self, **overrides):
        state = attachment.GoogleIdentityLineageState(**{**BASE, **overrides})
        return attachment.classify_google_identity_lineage(state)

    def test_legacy_transport_does_not_grant_canonical_authority(self):
        result = self.classify()
        self.assertEqual(result["status"], "BLOCKED_OAUTH_CONSUMER_BINDING")
        self.assertEqual(
            result["target"]["role"],
            "CANONICAL_PROVIDER_AUTHORITY_TARGET",
        )
        self.assertEqual(
            result["transport"]["role"],
            "LEGACY_CLOUDOPS_TRANSPORT_ONLY",
        )
        self.assertTrue(result["transport"]["legacy_transport_reuse_only"])
        self.assertFalse(result["transport"]["authority_inherited"])
        self.assertFalse(result["provider_authority_ready"])

    def test_target_change_does_not_repair_cloudops_oauth_consumer(self):
        result = self.classify(
            consumer_identity_verified=True,
            consumer_api_enabled=False,
        )
        self.assertTrue(result["target"]["canonical_match"])
        self.assertEqual(
            result["oauth_consumer"]["role"],
            "CLOUDOPS_OAUTH_CONSUMER_BLOCKED",
        )
        self.assertFalse(result["oauth_consumer"]["binding_ready"])
        self.assertFalse(
            result["invariants"]["target_change_repairs_oauth_consumer"]
        )
        self.assertFalse(result["provider_authority_ready"])

    def test_fogas_consumer_is_classified_separately(self):
        result = self.classify(
            oauth_consumer_project_number="979287460558",
            transport_project_number=None,
        )
        self.assertEqual(
            result["oauth_consumer"]["role"],
            "FOGAS_OAUTH_CONSUMER_BLOCKED",
        )
        self.assertEqual(
            result["transport"]["role"],
            "NO_PROJECT_LINEAGE",
        )
        self.assertEqual(result["status"], "BLOCKED_OAUTH_CONSUMER_BINDING")

    def test_public_web_app_approval_default_is_security_hold(self):
        result = self.classify(
            consumer_identity_verified=True,
            consumer_api_enabled=True,
            target_authority_verified=True,
            token_issued=True,
            provider_authenticated=True,
            semantic_readback_verified=True,
            deployment_inventory_verified=True,
            active_principal="redacted-principal",
            public_web_app=True,
            approval_default_injected=True,
        )
        self.assertEqual(
            result["status"],
            "SECURITY_HOLD_PUBLIC_APPROVAL_BYPASS",
        )
        self.assertTrue(result["security"]["public_approval_bypass"])
        self.assertFalse(result["provider_authority_ready"])

    def test_distinct_consumer_can_be_ready_for_cloud_resource_admin(self):
        result = self.classify(
            route_class=attachment.ROUTE_GOOGLE_CLOUD_RESOURCE_ADMIN,
            oauth_consumer_project_number="979287460558",
            transport_project_number=None,
            consumer_identity_verified=True,
            consumer_api_enabled=True,
            target_authority_verified=True,
            token_issued=True,
            provider_authenticated=True,
            semantic_readback_verified=True,
            deployment_inventory_verified=True,
            active_principal="redacted-principal",
        )
        self.assertFalse(
            result["invariants"]["consumer_project_must_equal_target_project"]
        )
        self.assertTrue(result["oauth_consumer"]["binding_ready"])
        self.assertEqual(result["status"], "PROVIDER_AUTHORITY_VERIFIED")
        self.assertTrue(result["provider_authority_ready"])
        self.assertFalse(
            result["provider_mutation_authorized_by_this_receipt"]
        )

    def test_scripts_run_rejects_distinct_consumer_even_with_other_proof(self):
        result = self.classify(
            route_class=attachment.ROUTE_APPS_SCRIPT_SCRIPTS_RUN,
            oauth_consumer_project_number="979287460558",
            transport_project_number=None,
            consumer_identity_verified=True,
            consumer_api_enabled=True,
            apps_script_api_access_granted=True,
            standard_cloud_project_shared=True,
            target_authority_verified=True,
            token_issued=True,
            provider_authenticated=True,
            semantic_readback_verified=True,
            deployment_inventory_verified=True,
            active_principal="redacted-principal",
        )
        self.assertEqual(
            result["status"],
            "BLOCKED_ROUTE_PROJECT_RELATIONSHIP",
        )
        self.assertFalse(result["route"]["consumer_target_same"])
        self.assertFalse(result["route"]["relationship_ready"])
        self.assertFalse(result["provider_authority_ready"])

    def test_scripts_run_accepts_only_common_standard_project_after_proof(self):
        result = self.classify(
            route_class=attachment.ROUTE_APPS_SCRIPT_SCRIPTS_RUN,
            oauth_consumer_project_number="257649435135",
            transport_project_number=None,
            consumer_identity_verified=True,
            consumer_api_enabled=True,
            apps_script_api_access_granted=True,
            standard_cloud_project_shared=True,
            target_authority_verified=True,
            token_issued=True,
            provider_authenticated=True,
            semantic_readback_verified=True,
            deployment_inventory_verified=True,
            active_principal="redacted-principal",
        )
        self.assertTrue(result["route"]["consumer_target_same"])
        self.assertTrue(result["route"]["relationship_ready"])
        self.assertEqual(result["status"], "PROVIDER_AUTHORITY_VERIFIED")

    def test_project_management_requires_explicit_apps_script_api_access(self):
        result = self.classify(
            route_class=attachment.ROUTE_APPS_SCRIPT_PROJECT_MANAGEMENT,
            consumer_identity_verified=True,
            consumer_api_enabled=True,
            apps_script_api_access_granted=False,
        )
        self.assertEqual(
            result["status"],
            "BLOCKED_ROUTE_PROJECT_RELATIONSHIP",
        )
        self.assertFalse(result["route"]["relationship_ready"])

    def test_authentication_without_token_proof_fails_closed(self):
        with self.assertRaisesRegex(
            attachment.AttachmentError,
            "token issuance",
        ):
            self.classify(provider_authenticated=True)

    def test_unproved_provider_mutation_is_an_incident_state(self):
        result = self.classify(provider_mutation_performed=True)
        self.assertEqual(
            result["status"],
            "PROVIDER_MUTATION_WITHOUT_AUTHORITY_PROOF",
        )
        self.assertFalse(result["provider_authority_ready"])
        self.assertEqual(
            result["next_gate"],
            "CONTAIN_PRESERVE_AND_INDEPENDENTLY_READ_BACK",
        )


if __name__ == "__main__":
    unittest.main()
