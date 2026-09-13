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
        self.assertIn("ADMITTED_SOURCE_SHA: 8125c6997830c97649c379d68e957da0afcaa091", self.text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$ADMITTED_SOURCE_SHA"', self.text)

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

    def test_semantic_fail_closed_court_uses_authenticated_proxy(self):
        for token in (
            'gcloud run services proxy "$CANARY_SERVICE"',
            "/healthz",
            "/node",
            "/mcp",
            "/agent/enroll/start",
            "RELAY_PROVIDER_VERIFIED=true",
        ):
            self.assertIn(token, self.text)

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
