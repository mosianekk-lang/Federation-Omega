from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ".github/workflows/fuse-mobile-gateway-zero-traffic-v1.yml"
WORKFLOW = ROOT / WORKFLOW_PATH
POLICY = ROOT / "governance" / "github_airlock_policy.json"
AIRLOCK = ROOT / "tools" / "github_airlock.py"


class FuseMobileGatewayDeployWorkflowV1Tests(unittest.TestCase):
    def _workflow_or_skip_export(self) -> str:
        if not WORKFLOW.is_file():
            self.skipTest("provider workflow controls are outside the reduced Phoenix exported-core surface")
        return WORKFLOW.read_text()

    def test_owner_only_keyless_provider_effect_boundary(self) -> None:
        text = self._workflow_or_skip_export()
        self.assertIn("[FO-DISPATCH] FUSE_MOBILE_GATEWAY_ZERO_TRAFFIC_V1", text)
        self.assertIn("author_association == 'OWNER'", text)
        self.assertIn("contents: read", text)
        self.assertIn("issues: read", text)
        self.assertIn("id-token: write", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("workload_identity_provider", text)
        self.assertNotIn("credentials_json", text)

    def test_build_push_and_deploy_are_explicit_provider_effects(self) -> None:
        text = self._workflow_or_skip_export()
        self.assertIn("docker build", text)
        self.assertIn("docker push", text)
        self.assertIn("gcloud run deploy", text)
        self.assertIn("--no-allow-unauthenticated", text)
        self.assertNotIn("--allow-unauthenticated", text)
        self.assertNotIn("update-traffic --to-latest", text)
        self.assertIn("provider_mutation_performed':True", text)

    def test_existing_service_uses_zero_percent_tagged_revision(self) -> None:
        text = self._workflow_or_skip_export()
        self.assertIn("--no-traffic", text)
        self.assertIn("EXISTING_SERVICE_ZERO_PERCENT_TAGGED", text)
        self.assertIn("assert new_percent==0", text)
        self.assertIn("production_traffic_changed':False", text)

    def test_new_service_is_truthfully_classified_private_first_revision(self) -> None:
        text = self._workflow_or_skip_export()
        self.assertIn("NEW_PRIVATE_FIRST_REVISION_CANARY", text)
        self.assertIn("service_existed_before", text)
        self.assertIn("public_invocation':False", text)
        self.assertIn("new_percent in {0,100}", text)

    def test_secretless_firestore_session_dependency_is_fail_closed(self) -> None:
        text = self._workflow_or_skip_export()
        self.assertIn("FIRESTORE_HASH_ONLY_OPAQUE", text)
        self.assertIn("runtime_firestore_authority", text)
        self.assertIn("firestore-database.json", text)
        self.assertIn("existing_session_invalid_after_device_revoke", text)
        self.assertIn("SESSION_DEVICE_REVOKED", text)
        self.assertIn("PRIVATE_GATEWAY_F134_SECRETLESS_RUNTIME_E2E_VERIFIED", text)
        self.assertIn("PRIVATE_GATEWAY_CANARY_DEPLOYED_SOURCE_READY", text)
        self.assertIn("vertex_semantic_inference':'HELD_UNPROVEN_NOT_EXECUTED'", text)
        self.assertNotIn("FUSE_MOBILE_SESSION_SECRET_B64", text)
        self.assertNotIn("SESSION_SECRET_ID", text)
        self.assertNotIn("--set-secrets", text)
        self.assertNotIn("gcloud secrets", text)
        self.assertNotIn("secretmanager.googleapis.com", text)
        self.assertNotIn("secretAccessor", text)

    def test_provider_native_health_and_iam_readback_are_required(self) -> None:
        text = self._workflow_or_skip_export()
        self.assertIn("services get-iam-policy", text)
        self.assertIn("projects get-iam-policy", text)
        self.assertIn("token_format: id_token", text)
        self.assertIn(
            "id_token_audience: https://fuse-mobile-gateway-257649435135.africa-south1.run.app",
            text,
        )
        self.assertIn("ID_TOKEN: ${{ steps.auth.outputs.id_token }}", text)
        self.assertNotIn("gcloud auth print-identity-token", text)
        self.assertIn("$CANARY_URL/health", text)
        self.assertIn("deployment-receipt.json", text)
        self.assertIn("Upload immutable provider proof, including partial evidence on failure", text)
        self.assertIn("if: always()", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)

    def test_airlock_classifies_and_constrains_fuse_mobile_deployment(self) -> None:
        if not POLICY.is_file() or not AIRLOCK.is_file():
            self.skipTest("Airlock governance is outside the reduced Phoenix exported-core surface")
        policy = json.loads(POLICY.read_text())
        airlock = AIRLOCK.read_text()
        self.assertIn(WORKFLOW_PATH, policy["active_workflow_allowlist"])
        self.assertEqual(policy["allowed_events"][WORKFLOW_PATH], ["issues"])
        self.assertIn(WORKFLOW_PATH, policy["oidc_workflow_allowlist"])
        self.assertIn(WORKFLOW_PATH, policy["provider_mutation_workflow_allowlist"])
        self.assertEqual(
            policy["provider_mutation_exact_issue_titles"][WORKFLOW_PATH],
            "[FO-DISPATCH] FUSE_MOBILE_GATEWAY_ZERO_TRAFFIC_V1",
        )
        self.assertIn("--no-allow-unauthenticated", policy["provider_mutation_required_markers"][WORKFLOW_PATH])
        self.assertIn("--allow-unauthenticated", policy["provider_mutation_forbidden_markers"][WORKFLOW_PATH])
        self.assertIn('"gcloud run deploy"', airlock)
        self.assertIn('"docker push"', airlock)
        self.assertIn("PROVIDER_MUTATION_REQUIRED_GUARD_MISSING", airlock)
        self.assertIn("PROVIDER_MUTATION_FORBIDDEN_BEHAVIOR", airlock)


if __name__ == "__main__":
    unittest.main()
