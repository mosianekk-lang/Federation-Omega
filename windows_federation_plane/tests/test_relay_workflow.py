from __future__ import annotations

from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "fuse-windows-relay-cloud-run-v1.yml"


class RelayWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_owner_only_default_deny_dispatch(self):
        self.assertIn("author_association == 'OWNER'", self.text)
        self.assertIn("[FO-DISPATCH] FUSE_WINDOWS_RELAY_CLOUD_RUN_V2", self.text)
        self.assertRegex(self.text, r"permissions:\n  contents: read\n  issues: read\n  id-token: write")
        self.assertIn("cancel-in-progress: false", self.text)

    def test_third_party_actions_are_sha_pinned(self):
        uses = re.findall(r"^\s*uses:\s*([^\s]+)", self.text, flags=re.MULTILINE)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40}$")
        self.assertIn("persist-credentials: false", self.text)

    def test_existing_service_keeps_tagged_zero_traffic_canary_and_rollback(self):
        self.assertIn("TAGGED_ZERO_TRAFFIC_EXISTING_SERVICE", self.text)
        self.assertIn("--no-traffic --tag relay-canary", self.text)
        self.assertIn("/healthz", self.text)
        self.assertIn("$SEMANTIC_URL/mcp", self.text)
        self.assertIn("--to-revisions=\"$CANARY_REVISION=100\"", self.text)
        self.assertIn("if: failure() && env.PRODUCTION_SERVICE_PRESENT == 'true'", self.text)
        self.assertLess(self.text.index("$candidate/healthz"), self.text.index("$CANARY_REVISION=100"))

    def test_absent_service_uses_separate_isolated_canary_without_fake_zero_traffic(self):
        self.assertIn("ISOLATED_CANARY_SERVICE_WHEN_PRODUCTION_ABSENT", self.text)
        self.assertIn('TARGET_SERVICE="${SERVICE}-canary-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"', self.text)
        isolated_deploy = re.search(
            r'gcloud run deploy "\$TARGET_SERVICE"[^\n]+',
            self.text,
        )
        self.assertIsNotNone(isolated_deploy)
        self.assertNotIn("--no-traffic", isolated_deploy.group(0))
        self.assertIn("--min 0 --max 1", isolated_deploy.group(0))
        self.assertIn("--ingress all", isolated_deploy.group(0))
        self.assertIn("--default-url", isolated_deploy.group(0))
        self.assertIn("--no-invoker-iam-check", isolated_deploy.group(0))
        self.assertIn("PRODUCTION_SERVICE_UNEXPECTEDLY_CREATED", self.text)
        self.assertIn("PRODUCTION_ISOLATION_CHECKED=true", self.text)
        self.assertIn("CANARY_DELETE_POINTER=gcloud run services delete", self.text)
        self.assertIn('"production_isolation_checked": truth("PRODUCTION_ISOLATION_CHECKED")', self.text)
        self.assertIn('"canary_delete_pointer": os.environ.get("CANARY_DELETE_POINTER")', self.text)

    def test_promotion_cannot_target_isolated_first_service(self):
        self.assertIn(
            "if: env.ALLOW_PRODUCTION_PROMOTION == 'true' && env.PRODUCTION_SERVICE_PRESENT == 'true'",
            self.text,
        )
        self.assertIn("PRODUCTION_TRAFFIC_CHANGED=false", self.text)
        self.assertIn("PRODUCTION_TRAFFIC_CHANGED=true", self.text)
        self.assertIn('"production_traffic_changed": truth("PRODUCTION_TRAFFIC_CHANGED")', self.text)

    def test_agent_only_is_secret_manager_independent(self):
        self.assertIn("FUSE Windows Relay Cloud Run v2.4", self.text)
        self.assertIn("DEVICE_AUTH_MODE=ECDSA_P256_PUBLIC_KEY", self.text)
        self.assertIn('"secret_manager_required": False', self.text)
        self.assertNotIn("--set-secrets=", self.text)
        self.assertNotIn("gcloud secrets", self.text)
        self.assertNotIn("add-iam-policy-binding", self.text)
        self.assertNotIn("gcloud services enable", self.text)
        self.assertIn('"secret_value_recorded": False', self.text)
        self.assertIn("BROWSER_ENTRYPOINT_CHECKED=true", self.text)
        self.assertIn("MCP_FAIL_CLOSED_CHECKED=true", self.text)

    def test_cloud_run_env_satisfies_relay_server_project_precondition(self):
        self.assertIn(
            'ENVVARS="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FUSE_AGENT_ONLY_BOOTSTRAP=true,FUSE_DEVICE_AUTH_MODE=ECDSA_P256_PUBLIC_KEY"',
            self.text,
        )
        self.assertIn(
            'ENVVARS="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FUSE_OIDC_ISSUER=$OIDC_ISSUER,FUSE_OIDC_JWKS_URL=$OIDC_JWKS_URL,FUSE_MCP_RESOURCE_URL=https://bootstrap.invalid/mcp,FUSE_DEVICE_AUTH_MODE=ECDSA_P256_PUBLIC_KEY"',
            self.text,
        )
        self.assertEqual(self.text.count("GOOGLE_CLOUD_PROJECT=$PROJECT_ID"), 3)
        self.assertIn('--set-env-vars="$ENVVARS"', self.text)

    def test_health_route_differential_is_bounded_and_drives_semantic_checks(self):
        self.assertIn(
            'DETERMINISTIC_URL="https://${TARGET_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"',
            self.text,
        )
        self.assertIn('CANDIDATE_URLS=("$CANARY_URL" "$SERVICE_URL" "$DETERMINISTIC_URL")', self.text)
        self.assertIn("for attempt in $(seq 1 12)", self.text)
        self.assertIn("--connect-timeout 5 --max-time 10", self.text)
        self.assertIn("HEALTH_ROUTE_DIFFERENTIAL_CHECKED=true", self.text)
        self.assertIn('echo "SEMANTIC_URL=$SEMANTIC_URL" >> "$GITHUB_ENV"', self.text)
        self.assertIn('"$SEMANTIC_URL/mcp"', self.text)
        self.assertIn('"$SEMANTIC_URL/node"', self.text)
        self.assertIn('"$SEMANTIC_URL/node/worker.js"', self.text)
        self.assertIn('"$SEMANTIC_URL/node/native-bootstrap.ps1"', self.text)
        self.assertNotIn('curl --fail --silent --show-error "$CANARY_URL/healthz"', self.text)

    def test_edge_app_differential_falsifies_edge_vs_application_without_iam_widening(self):
        self.assertIn("EDGE_APP_DIFFERENTIAL_CHECKED=true", self.text)
        self.assertIn('gcloud run services proxy "$TARGET_SERVICE"', self.text)
        self.assertIn("PROXY_PORT=18081", self.text)
        self.assertIn("EDGE_ACCESS_OR_INGRESS_404_APP_HEALTH_VIA_AUTH_PROXY", self.text)
        self.assertIn("APPLICATION_ROUTE_OR_PROXY_PATH_UNHEALTHY", self.text)
        self.assertIn("AUTHENTICATED_PROXY_UNCALLABLE", self.text)
        self.assertIn("run.googleapis.com/ingress", self.text)
        self.assertIn("run.googleapis.com/default-url-disabled", self.text)
        self.assertIn("run.googleapis.com/invoker-iam-disabled", self.text)
        self.assertIn("gcloud logging read", self.text)
        self.assertNotIn("set-iam-policy", self.text)
        self.assertNotIn("add-iam-policy-binding", self.text)

    def test_exact_image_localhost_differential_precedes_cloud_run_deployment(self):
        local_step = "Exact-image localhost differential before provider deployment"
        deploy_step = "Deploy isolated-first-service or zero-traffic existing-service canary"
        self.assertIn(local_step, self.text)
        self.assertLess(self.text.index(local_step), self.text.index(deploy_step))
        self.assertIn('docker pull "$IMAGE_DIGEST_URI"', self.text)
        self.assertIn('"$IMAGE_DIGEST_URI" >/dev/null', self.text)
        self.assertIn('"http://127.0.0.1:${LOCAL_PORT}/healthz"', self.text)
        self.assertIn('"http://127.0.0.1:${LOCAL_PORT}/node"', self.text)
        self.assertIn('"http://127.0.0.1:${LOCAL_PORT}/mcp"', self.text)
        self.assertIn('"http://127.0.0.1:${LOCAL_PORT}/agent/enroll/start"', self.text)
        self.assertIn("LOCAL_PAIR_RESPONSE_MISSING", self.text)
        self.assertIn("LOCAL_PAIR_CONTRACT_OBSERVED", self.text)
        self.assertIn("PAIRING_GRANT_ID_INVALID", self.text)
        self.assertIn("LOCAL_MCP_FAIL_CLOSED_REQUIRED", self.text)
        self.assertIn('from federation_windows_plane.mcp_service import server_from_env', self.text)
        for route in ("/mcp", "/agent/enroll/start", "/agent/enroll/complete", "/agent/runtime/poll", "/agent/runtime/complete"):
            self.assertIn(route, self.text)
        self.assertIn("_custom_starlette_routes", self.text)
        self.assertNotIn("--network host", self.text)
        self.assertNotIn("cat \"$GOOGLE_APPLICATION_CREDENTIALS\"", self.text)

    def test_receipt_binds_exact_source_provider_image_revision_topology_and_differential(self):
        self.assertIn('"schema": "FUSE-WINDOWS-RELAY-DEPLOYMENT-RECEIPT-V27"', self.text)
        for field in (
            '"source_sha"',
            '"image_digest_uri"',
            '"local_image_differential_checked"',
            '"local_health_code"',
            '"local_node_code"',
            '"local_mcp_code"',
            '"local_pair_code"',
            '"local_health_sha256"',
            '"local_node_sha256"',
            '"local_routes_sha256"',
            '"local_startup_log_sha256"',
            '"local_pair_sha256"',
            '"canary_revision"',
            '"canary_url"',
            '"semantic_url"',
            '"target_service"',
            '"deployment_topology"',
            '"production_service_present"',
            '"health_route_differential_checked"',
            '"edge_app_differential_checked"',
            '"edge_health_code"',
            '"proxy_health_code"',
            '"edge_failure_class"',
            '"ingress_setting"',
            '"default_url_disabled"',
            '"invoker_iam_disabled"',
            '"request_log_count"',
        ):
            self.assertIn(field, self.text)


if __name__ == "__main__":
    unittest.main()
