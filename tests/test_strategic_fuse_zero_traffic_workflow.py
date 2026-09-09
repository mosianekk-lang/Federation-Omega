from __future__ import annotations

import unittest
from pathlib import Path


class StrategicFuseZeroTrafficWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow_path = Path(__file__).resolve().parents[1] / ".github/workflows/strategic-fuse-appsscript-read-zero-traffic.yml"
        if not cls.workflow_path.exists():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.text = cls.workflow_path.read_text(encoding="utf-8")
        cls.low = cls.text.lower()

    def test_required_boundaries_present(self) -> None:
        required = [
            "issues:",
            "types: [opened]",
            "github.event.issue.title == '[FO-DISPATCH] STRATEGIC_FUSE_APPS_SCRIPT_READ_ZERO_TRAFFIC_V1'",
            "github.event.issue.author_association == 'OWNER'",
            "id-token: write",
            "issues: read",
            "superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com",
            "superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com",
            "READ_APPS_SCRIPT_PROJECT_BOUNDED",
            "1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R",
            "OPERATOR_AUDIENCE",
            "OIDC_ALLOWED_PRINCIPALS",
            "CANDIDATE_OIDC_ALLOWED_PRINCIPALS",
            "metadata_name = str(p.get('metadata', {}).get('name') or '').strip()",
            "OPERATOR_SERVICE_IDENTITY_DRIFT",
            "canonical_url = str(p.get('status', {}).get('url') or '').strip()",
            "OPERATOR_CANONICAL_URL_SERVICE_BINDING_INVALID",
            "OPERATOR_HOST_SHA256",
            "roles/artifactregistry.writer",
            "ARTIFACT_REGISTRY_WRITER_PREEXISTING_REQUIRED",
            "roles/iam.serviceAccountUser",
            "CANDIDATE_RUNTIME_ACTAS_PREEXISTING_REQUIRED",
            "CANDIDATE_RUNTIME_IDENTITY_DRIFT",
            "--service-account \"$CANDIDATE_RUNTIME_SA\"",
            '--remove-secrets "FO_ADMIN_TOKEN"',
            "CANDIDATE_RUNTIME_IDENTITY_MISMATCH",
            "gcloud auth configure-docker",
            "docker build --pull",
            "docker push \"$IMAGE_TAG\"",
            "gcloud artifacts docker images describe \"$IMAGE_TAG\"",
            "--no-traffic",
            "--tag \"$TAG\"",
            "TAG=\"sf-${GITHUB_SHA:0:8}\"",
            "CLOUD_RUN_SERVICE_TAG_LENGTH_EXCEEDS_46",
            "--set-env-vars \"OPERATOR_AUDIENCE=${OPERATOR_AUDIENCE},OIDC_ALLOWED_PRINCIPALS=${CANDIDATE_OIDC_ALLOWED_PRINCIPALS}\"",
            "CANDIDATE_SECRET_BACKED_ENV_FORBIDDEN",
            "CANDIDATE_ENV_NOT_CLOSED_WORLD",
            "gcloud auth print-identity-token",
            "--include-email",
            "\"action\":\"STATUS\"",
            "'action': os.environ['REQUIRED_ACTION']",
            "--data-binary @/tmp/strategic-read/read-request.json",
            "'APPS_SCRIPT_PROJECT_BOUNDED_READ_VERIFIED'",
            "'rawSourcePersisted'",
            "'sourceReturned'",
            "'providerEffect'",
            "'mutationAttempted'",
            "'secretValuesRecorded'",
            "SERVING_TRAFFIC_CHANGED",
            "CANDIDATE_NOT_ZERO_TRAFFIC_AT_END",
            "'candidate_traffic_percent':0",
            "'serving_traffic_unchanged':True",
            "'provider_native_audience':True",
            "'artifact_registry_writer_preexisting':",
            "'candidate_runtime_service_account':",
            "'candidate_runtime_actas_preexisting':",
            "'image_build_transport':'GITHUB_HOSTED_DOCKER_DIRECT_ARTIFACT_REGISTRY'",
            "'cloud_build_staging_used':False",
            "'candidate_environment_closed_world':True",
            "'candidate_secret_backed_env_count':0",
            "'candidate_only_trust_binding':True",
            "'service_template_mutation_performed':True",
            "'serving_revision_runtime_identity_mutation_performed':False",
            "'serving_revision_trust_mutation_performed':False",
            "'iam_mutation_performed':False",
            "'wif_mutation_performed':False",
            "'traffic_promotion_performed':False",
            "'provider_effect_scope':'ZERO_TRAFFIC_CANDIDATE_REVISION_ONLY'",
        ]
        missing = [item for item in required if item not in self.text]
        self.assertFalse(missing, missing)

    def test_stale_hardcoded_operator_url_is_not_runtime_authority(self) -> None:
        self.assertNotIn("OPERATOR_URL:", self.text)
        self.assertNotIn("OPERATOR_CANONICAL_URL_DRIFT", self.text)
        self.assertNotIn("canonical_url == os.environ['OPERATOR_URL']", self.text)

    def test_provider_native_service_identity_is_exact(self) -> None:
        self.assertIn("metadata_name = str(p.get('metadata', {}).get('name') or '').strip()", self.text)
        self.assertIn(
            "assert metadata_name == os.environ['OPERATOR_SERVICE'], 'OPERATOR_SERVICE_IDENTITY_DRIFT'",
            self.text,
        )
        self.assertIn("gcloud run services describe \"$OPERATOR_SERVICE\"", self.text)
        self.assertIn("--project \"$PROJECT_ID\" --region \"$REGION\" --format=json", self.text)

    def test_provider_native_audience_is_bounded_to_service_run_app_host(self) -> None:
        self.assertIn("canonical_url = str(p.get('status', {}).get('url') or '').strip()", self.text)
        self.assertIn("assert canonical_url, 'OPERATOR_CANONICAL_URL_MISSING'", self.text)
        self.assertIn("expected_prefix = os.environ['OPERATOR_SERVICE'].lower() + '-'", self.text)
        self.assertIn("assert parsed.scheme == 'https', 'OPERATOR_CANONICAL_URL_SCHEME_INVALID'", self.text)
        self.assertIn("OPERATOR_CANONICAL_URL_AUTHORITY_INVALID", self.text)
        self.assertIn("OPERATOR_CANONICAL_URL_SHAPE_INVALID", self.text)
        self.assertIn("host.startswith(expected_prefix) and host.endswith('.run.app')", self.text)
        self.assertIn("fh.write('OPERATOR_AUDIENCE<<STRATEGIC_AUD_EOF", self.text)

    def test_preexisting_application_trust_is_not_required(self) -> None:
        self.assertNotIn("OPERATOR_AUDIENCE_PREEXISTING_REQUIRED", self.text)
        self.assertNotIn("OIDC_ALLOWED_PRINCIPALS_PREEXISTING_REQUIRED", self.text)
        self.assertNotIn("DEPLOYER_NOT_PREEXISTING_OIDC_PRINCIPAL", self.text)
        self.assertIn("SERVING_AUDIENCE_PRESENT", self.text)
        self.assertIn("SERVING_PRINCIPAL_COUNT", self.text)

    def test_build_transport_avoids_cloud_build_staging_bucket(self) -> None:
        self.assertNotIn("gcloud builds submit", self.text)
        self.assertNotIn("_cloudbuild/source", self.text)
        self.assertIn("gcloud auth configure-docker", self.text)
        self.assertIn("docker build --pull", self.text)
        self.assertIn('docker push "$IMAGE_TAG"', self.text)
        self.assertIn('gcloud artifacts docker images describe "$IMAGE_TAG"', self.text)
        self.assertLess(self.text.index('docker push "$IMAGE_TAG"'), self.text.index('gcloud run deploy "$OPERATOR_SERVICE"'))

    def test_existing_provider_authority_is_reproved_before_candidate_deploy(self) -> None:
        self.assertIn('gcloud projects get-iam-policy "$PROJECT_ID"', self.text)
        self.assertIn('gcloud artifacts repositories get-iam-policy "$REPOSITORY"', self.text)
        self.assertIn('gcloud iam service-accounts describe "$CANDIDATE_RUNTIME_SA"', self.text)
        self.assertIn('gcloud iam service-accounts get-iam-policy "$CANDIDATE_RUNTIME_SA"', self.text)
        self.assertIn("roles/artifactregistry.writer", self.text)
        self.assertIn("roles/iam.serviceAccountUser", self.text)
        self.assertIn("ARTIFACT_REGISTRY_WRITER_PREEXISTING_REQUIRED", self.text)
        self.assertIn("CANDIDATE_RUNTIME_ACTAS_PREEXISTING_REQUIRED", self.text)
        self.assertLess(self.text.index("CANDIDATE_RUNTIME_ACTAS_PREEXISTING_REQUIRED"), self.text.index('gcloud run deploy "$OPERATOR_SERVICE"'))
        self.assertNotIn("add-iam-policy-binding", self.low)

    def test_candidate_removes_exact_inherited_admin_secret_before_creation(self) -> None:
        deploy = self.text.index('gcloud run deploy "$OPERATOR_SERVICE"')
        remove = self.text.index('--remove-secrets "FO_ADMIN_TOKEN"', deploy)
        env = self.text.index("--set-env-vars", deploy)
        self.assertLess(deploy, remove)
        self.assertLess(remove, env)
        self.assertEqual(1, self.text.count('--remove-secrets "FO_ADMIN_TOKEN"'))
        self.assertNotIn("--clear-secrets", self.text)
        self.assertNotIn("--set-secrets", self.text)
        self.assertNotIn("--update-secrets", self.text)

    def test_candidate_uses_only_pre_authorized_runtime_identity(self) -> None:
        self.assertIn("CANDIDATE_RUNTIME_SA: superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com", self.text)
        self.assertIn('--service-account "$CANDIDATE_RUNTIME_SA"', self.text)
        self.assertIn("CANDIDATE_RUNTIME_IDENTITY_MISMATCH", self.text)
        self.assertNotIn('--service-account "fo-operator-sa@sov-hybrid-suite.iam.gserviceaccount.com"', self.text)

    def test_candidate_principal_is_exact_authenticated_deployer_only(self) -> None:
        self.assertIn("candidate_principals = deployer", self.text)
        self.assertIn("fh.write('CANDIDATE_OIDC_ALLOWED_PRINCIPALS=' + candidate_principals", self.text)
        self.assertIn(
            "assert allowed == [os.environ['DEPLOYER_SA'].lower()], 'CANDIDATE_PRINCIPAL_DRIFT'",
            self.text,
        )

    def test_candidate_trust_synthesis_is_closed_world_zero_traffic_only(self) -> None:
        self.assertEqual(1, self.text.count("--set-env-vars"))
        self.assertNotIn("--update-env-vars", self.text)
        self.assertIn(
            '--set-env-vars "OPERATOR_AUDIENCE=${OPERATOR_AUDIENCE},OIDC_ALLOWED_PRINCIPALS=${CANDIDATE_OIDC_ALLOWED_PRINCIPALS}"',
            self.text,
        )
        self.assertIn("assert not secret_backed, 'CANDIDATE_SECRET_BACKED_ENV_FORBIDDEN'", self.text)
        self.assertIn(
            "assert set(direct) == {'OPERATOR_AUDIENCE', 'OIDC_ALLOWED_PRINCIPALS'}",
            self.text,
        )
        self.assertLess(self.text.index("--set-env-vars"), self.text.index("/tmp/strategic-read/read-request.json"))

    def test_cloud_run_candidate_tag_is_deterministic_and_within_provider_limit(self) -> None:
        self.assertIn('TAG="sf-${GITHUB_SHA:0:8}"', self.text)
        self.assertIn('if (( ${#OPERATOR_SERVICE} + ${#TAG} > 46 )); then', self.text)
        self.assertIn("CLOUD_RUN_SERVICE_TAG_LENGTH_EXCEEDS_46", self.text)
        self.assertNotIn('TAG="strategic-read-${GITHUB_SHA:0:8}"', self.text)
        service = "federation-omega-operator"
        tag = "sf-" + ("0" * 8)
        self.assertLessEqual(len(service) + len(tag), 46)

    def test_forbidden_effect_routes_absent(self) -> None:
        forbidden = [
            "workflow_dispatch:",
            "inputs.confirmation",
            "fo-operator-admin-token",
            "gcloud secrets versions access",
            "${{ secrets.",
            "--update-env-vars",
            "--set-secrets",
            "--update-secrets",
            "run services update-traffic",
            "--to-revisions",
            "--to-tags",
            "--allow-unauthenticated",
            "allusers",
            "add-iam-policy-binding",
            "projects.updatecontent",
            "workload-identity-pools providers update",
            "workload-identity-pools providers create",
        ]
        bad = [item for item in forbidden if item.lower() in self.low]
        self.assertFalse(bad, bad)

    def test_one_strategic_read_request_execution(self) -> None:
        self.assertEqual(1, self.text.count("--data-binary @/tmp/strategic-read/read-request.json"))

    def test_status_precedes_strategic_read(self) -> None:
        self.assertLess(self.text.index("/tmp/strategic-read/status-request.json"), self.text.index("/tmp/strategic-read/read-request.json"))

    def test_no_traffic_is_proven_before_and_after_read(self) -> None:
        self.assertLess(self.text.index("CANDIDATE_TRAFFIC_NOT_ZERO"), self.text.index("/tmp/strategic-read/read-request.json"))
        self.assertLess(self.text.index("/tmp/strategic-read/read-request.json"), self.text.index("CANDIDATE_NOT_ZERO_TRAFFIC_AT_END"))

    def test_no_raw_source_is_persisted_in_receipt(self) -> None:
        self.assertIn("'project_digest':read.get('projectDigest')", self.text)
        self.assertIn("'raw_source_persisted':False", self.text)
        self.assertIn("'source_returned':False", self.text)
        self.assertIn("'source' in x", self.text)

    def test_provider_mutation_is_exact_owner_issue_gated(self) -> None:
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)
        self.assertIn("[FO-DISPATCH] STRATEGIC_FUSE_APPS_SCRIPT_READ_ZERO_TRAFFIC_V1", self.text)
        self.assertNotIn("workflow_dispatch:", self.text)


if __name__ == "__main__":
    unittest.main()
