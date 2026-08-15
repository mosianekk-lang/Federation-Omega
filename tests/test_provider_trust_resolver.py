from __future__ import annotations

import copy
import unittest

from federation_consolidation.provider_trust_resolver import (
    EVIDENCE_SCHEMA,
    ProviderTrustError,
    evidence_from_chatbridge_artifacts,
    resolve_provider_trust,
    validate_contract,
)


SHA = "a" * 64


class ProviderTrustResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = {
            "schema": "FEDOMEGA-PROVIDER-TRUST-CONTRACT-1",
            "contract_id": "TEST-TRUST-V1",
            "capabilities": {
                "OPENAI_PRIMARY_RUNTIME": {
                    "provider": "openai",
                    "bindings": [
                        {
                            "binding_id": "GITHUB",
                            "binding_type": "GITHUB_ACTIONS_REPOSITORY_SECRET_REFERENCE",
                            "reference": "github-actions:o/r:OPENAI_API_KEY",
                            "self_service_binding_available": False,
                            "secret_value_recorded": False,
                        },
                        {
                            "binding_id": "GSM",
                            "binding_type": "SECURE_CAPABILITY_BOX_GOOGLE_SECRET_MANAGER_REFERENCE",
                            "reference": "google-secret-manager:projects/p/secrets/OPENAI_API_KEY:7",
                            "self_service_binding_available": True,
                            "secret_value_recorded": False,
                        },
                    ],
                }
            },
        }
        validate_contract(self.contract)

    def evidence(self, **updates):
        base = {
            "schema": EVIDENCE_SCHEMA,
            "capability_alias": "OPENAI_PRIMARY_RUNTIME",
            "binding_id": "GITHUB",
            "credential_reference_found": True,
            "runtime_bound": True,
            "provider_authenticated": True,
            "provider_live_verified": False,
            "provider_error_code": None,
            "semantic_receipt_sha256": None,
            "archive_readback_verified": False,
            "archive_sha256": None,
            "outer_workflow_success": False,
            "secret_value_recorded": False,
        }
        base.update(updates)
        return base

    def test_live_verified_requires_inner_semantic_receipt(self):
        result = resolve_provider_trust(
            self.contract,
            self.evidence(provider_live_verified=True, semantic_receipt_sha256=SHA),
        )
        self.assertEqual(result["state"], "PROVIDER_LIVE_VERIFIED")
        self.assertTrue(result["ready"])
        self.assertFalse(result["owner_action_required"])

    def test_outer_workflow_green_does_not_promote_provider_truth(self):
        result = resolve_provider_trust(
            self.contract,
            self.evidence(
                provider_authenticated=False,
                provider_live_verified=False,
                outer_workflow_success=True,
            ),
        )
        self.assertEqual(result["state"], "RUNTIME_BOUND")
        self.assertFalse(result["provider_live_verified"])
        self.assertFalse(result["outer_workflow_success_is_promoting"])

    def test_credit_exhaustion_is_billing_not_rotation(self):
        result = resolve_provider_trust(
            self.contract,
            self.evidence(provider_error_code="credit_balance_exhausted"),
        )
        self.assertEqual(result["state"], "BLOCKED_PROVIDER_BILLING")
        self.assertEqual(result["next_action"], "RESTORE_PROVIDER_BILLING")
        self.assertTrue(result["owner_action_required"])
        self.assertFalse(result["credential_rotation_recommended"])

    def test_invalid_key_is_auth_failure_and_rotation_candidate(self):
        result = resolve_provider_trust(
            self.contract,
            self.evidence(
                provider_authenticated=False,
                provider_error_code="incorrect_api_key",
            ),
        )
        self.assertEqual(result["state"], "BLOCKED_PROVIDER_AUTH")
        self.assertTrue(result["credential_rotation_recommended"])

    def test_existing_self_service_reference_avoids_owner_prompt(self):
        result = resolve_provider_trust(
            self.contract,
            self.evidence(
                binding_id="GSM",
                runtime_bound=False,
                provider_authenticated=False,
            ),
        )
        self.assertEqual(result["state"], "CREDENTIAL_REFERENCE_FOUND")
        self.assertEqual(result["next_action"], "BIND_EXISTING_REFERENCE")
        self.assertFalse(result["owner_action_required"])

    def test_missing_reference_is_owner_bootstrap_only(self):
        evidence = self.evidence(
            binding_id=None,
            credential_reference_found=False,
            runtime_bound=False,
            provider_authenticated=False,
        )
        result = resolve_provider_trust(self.contract, evidence)
        self.assertEqual(result["state"], "BOOTSTRAP_REQUIRED")
        self.assertEqual(result["next_action"], "OWNER_BOOTSTRAP_CREDENTIAL_REFERENCE")
        self.assertTrue(result["owner_action_required"])

    def test_inconsistent_proof_ladder_fails_closed(self):
        with self.assertRaises(ProviderTrustError):
            resolve_provider_trust(
                self.contract,
                self.evidence(
                    credential_reference_found=False,
                    runtime_bound=True,
                ),
            )

    def test_raw_openai_secret_shape_is_rejected(self):
        evidence = self.evidence()
        evidence["note"] = "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
        with self.assertRaises(Exception):
            resolve_provider_trust(self.contract, evidence)

    def test_chatbridge_artifacts_map_to_live_ready(self):
        binding = {
            "key_bound": True,
            "key_source": "GITHUB_ACTIONS_SECRET",
            "direct_secret_present": True,
            "secret_values_recorded": False,
        }
        canary = {
            "state": "PROVIDER_LIVE_CANARY_PHASES_VERIFIED",
            "conversation_id": "conv_test",
            "duplicate_resume_rejected": True,
            "branch_provider_lineage_independent": True,
            "api_key_logged": False,
        }
        provider = {
            "provider_live_verified": True,
            "receipt_sha256": SHA,
            "classification": "PROVIDER_LIVE_VERIFIED",
            "api_key_logged": False,
        }
        evidence = evidence_from_chatbridge_artifacts(
            self.contract,
            binding_receipt=binding,
            canary_receipt=canary,
            provider_receipt=provider,
        )
        result = resolve_provider_trust(self.contract, evidence)
        self.assertEqual(evidence["binding_id"], "GITHUB")
        self.assertEqual(result["state"], "PROVIDER_LIVE_VERIFIED")

    def test_chatbridge_billing_error_is_authenticated_but_blocked(self):
        binding = {
            "key_bound": True,
            "key_source": "GITHUB_ACTIONS_SECRET",
            "direct_secret_present": True,
            "secret_values_recorded": False,
        }
        canary = {
            "state": "CANARY_FAILED",
            "child_error_code": "credit_balance_exhausted",
            "child_status_code": 429,
            "secret_values_recorded": False,
        }
        provider = {
            "provider_live_verified": False,
            "receipt_sha256": SHA,
            "classification": "RUNTIME_KEY_BOUND__PROVIDER_LIVE_CANARY_FAILED_OR_INCOMPLETE",
            "api_key_logged": False,
        }
        evidence = evidence_from_chatbridge_artifacts(
            self.contract,
            binding_receipt=binding,
            canary_receipt=canary,
            provider_receipt=provider,
        )
        result = resolve_provider_trust(self.contract, evidence)
        self.assertTrue(evidence["provider_authenticated"])
        self.assertEqual(result["state"], "BLOCKED_PROVIDER_BILLING")
        self.assertFalse(result["credential_rotation_recommended"])


if __name__ == "__main__":
    unittest.main()
