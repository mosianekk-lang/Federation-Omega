from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/fuse-windows-h1-provider-relay-v2.yml"


class WindowsH1ProviderRelayV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_machine_callable_and_exact_source(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotIn("issues:", self.text)
        self.assertIn("ref: ${{ inputs.source_sha }}", self.text)
        self.assertIn("description: Exact admitted F274 source commit", self.text)
        self.assertIn("ADMITTED_SOURCE_SHA: f22a627a841dd7297a137a56eb29d2b5de9acf9c", self.text)
        self.assertIn("EXPECTED_PACKET_ID: PKT-V5-WINDOWS-SCSF-RENDEZVOUS-PROVIDER-001", self.text)
        self.assertIn("WINDOWS_POLICY_EPOCH: FUSE_WINDOWS_SCSF_HARDWARE_ADAPTIVE_CNG_V1", self.text)
        self.assertNotIn("FUSE_WINDOWS_H1_TPM_PAIRING_V1", self.text)
        self.assertNotIn("PKT-V5-WINDOWS-H1-TPM-PAIRING-PROVIDER-001", self.text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$ADMITTED_SOURCE_SHA"', self.text)
        self.assertIn('echo "CONTROL_SHA=$GITHUB_SHA"', self.text)

    def test_action_specific_passport_is_hashed_typed_and_time_bounded(self):
        for token in (
            "provider_passport_json",
            "provider_passport_sha256",
            "FUSE-SURFACE-CAPABILITY-PASSPORT-V1",
            "A2_REVERSIBLE_ISOLATED_CANARY",
            "PASSPORT_FIELD_MISMATCH",
            "PASSPORT_TIME_WINDOW_INVALID",
        ):
            self.assertIn(token, self.text)

    def test_canary_is_unique_internal_authenticated_and_bounded(self):
        self.assertIn('CANARY_SERVICE="fuse-windows-h1-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}"', self.text)
        for token in ("--ingress internal", "--no-default-url", "--cpu 1", "--memory 512Mi", "--max 1"):
            self.assertIn(token, self.text)
        for forbidden in ("--ingress all", "--no-invoker-iam-check", "--allow-unauthenticated"):
            self.assertNotIn(forbidden, self.text)

    def test_no_preexisting_service_overwrite(self):
        self.assertIn("CANARY_NAME_COLLISION", self.text)
        self.assertIn('gcloud run services describe "$CANARY_SERVICE"', self.text)
        self.assertNotIn("SERVICE: fuse-windows-relay-h1", self.text)

    def test_provider_readback_and_executed_cleanup(self):
        for token in (
            "production-before.json",
            "production-after.json",
            "PRODUCTION_TRAFFIC_UNCHANGED=true",
            'gcloud run services delete "$CANARY_SERVICE"',
            "CANARY_CLEANUP_VERIFIED=true",
            "CANARY_CLEANUP_FAILED",
        ):
            self.assertIn(token, self.text)
        self.assertEqual(self.text.count("--format='json(status.traffic)'"), 2)
        self.assertNotIn("--format=json > /tmp/production", self.text)

    def test_semantic_proof_is_decomposed_without_impossible_external_proxy(self):
        for token in (
            "Exact-image local semantic differential",
            "docker run --detach",
            "/healthz",
            "/node",
            "/mcp",
            "/agent/enroll/start",
            "LOCAL_SEMANTICS_VERIFIED=true",
            "Provider readiness and config readback",
            "gcloud run revisions describe",
            "PROVIDER_RUNTIME_READY=true",
            "PROVIDER_CONFIG_VERIFIED=true",
            "PROVIDER_HTTP_ROUTE_VERIFIED=false",
            "EXACT_IMAGE_LOCAL_SEMANTICS_PLUS_INTERNAL_CLOUD_RUN_READINESS_CONFIG",
            '"owner_pc_internet_reachability":"OPEN_UNPROVEN"',
        ):
            self.assertIn(token, self.text)
        self.assertNotIn('gcloud run services proxy "$CANARY_SERVICE"', self.text)
        self.assertNotIn("RELAY_PROVIDER_VERIFIED=true", self.text)

    def test_runtime_source_and_control_currentness_are_distinct_receipt_fields(self):
        self.assertIn('"runtime_source_sha":os.environ["ADMITTED_SOURCE_SHA"]', self.text)
        self.assertIn('"control_sha":os.environ.get("CONTROL_SHA")', self.text)
        self.assertIn('"source_currentness_relation":"RUNTIME_SOURCE_PINNED__CONTROL_SHA_SEPARATE"', self.text)
        self.assertIn('"provider_http_route_verified":truth("PROVIDER_HTTP_ROUTE_VERIFIED")', self.text)

    def test_gcp_is_light_control_plane_only(self):
        self.assertIn('"gcp_heavy_compute":"DENY"', self.text)
        self.assertIn('"heavy_compute_performed":False', self.text)
        self.assertIn("docker build", self.text)
        self.assertNotIn("gcloud builds submit", self.text)
        for token in ("vertex", "dataflow", "compute instances", "gcloud batch"):
            self.assertNotIn(token, self.text.lower())

    def test_no_secret_or_iam_widening_surface(self):
        self.assertIn('"secret_value_recorded":False', self.text)
        self.assertIn('"iam_mutation_performed":False', self.text)
        for forbidden in ("gcloud secrets versions access", "add-iam-policy-binding", "remove-iam-policy-binding"):
            self.assertNotIn(forbidden, self.text)


if __name__ == "__main__":
    unittest.main()
