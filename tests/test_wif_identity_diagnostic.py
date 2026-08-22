import importlib.util
import json
import pathlib
import unittest
import urllib.parse


MODULE_PATH = pathlib.Path(__file__).parents[1] / "scripts" / "wif_identity_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("wif_identity_diagnostic", MODULE_PATH)
diagnostic = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(diagnostic)


VALID_PROVIDER = (
    "projects/123456789/locations/global/workloadIdentityPools/"
    "github-pool/providers/github-provider"
)
PROJECT_ID = "example-project"
SERVICE_ACCOUNT = "diagnostic@example-project.iam.gserviceaccount.com"
ENVIRONMENT = {
    "GITHUB_REPOSITORY": "owner/repository",
    "GITHUB_REF": "refs/heads/diagnostic",
    "GITHUB_SHA": "a" * 40,
    "SOURCE_HEAD_SHA": "b" * 40,
}


class WifIdentityDiagnosticTests(unittest.TestCase):
    def test_valid_provider_resource_is_parsed(self):
        parsed = diagnostic.parse_provider_resource(VALID_PROVIDER)
        self.assertEqual(parsed["project_number"], "123456789")
        self.assertEqual(parsed["pool"], "github-pool")
        self.assertEqual(parsed["provider"], "github-provider")

    def test_invalid_provider_resource_is_blocked_before_oidc(self):
        receipt = diagnostic.run_diagnostic(
            "projects/example/providers/incomplete", PROJECT_ID, SERVICE_ACCOUNT, {}
        )
        self.assertEqual(receipt["classification"], "WIF_CONFIGURATION_INVALID")
        self.assertFalse(receipt["oidc_token_requested"])
        self.assertFalse(receipt["google_sts_invoked"])

    def test_github_oidc_audience_matches_auth_action_contract(self):
        url = diagnostic._github_oidc_url(
            "https://example.invalid/oidc?api-version=2.0", VALID_PROVIDER
        )
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["audience"], [VALID_PROVIDER])

    def test_receipt_binds_source_head_separately_from_workflow_sha(self):
        receipt = diagnostic.make_base_receipt(
            VALID_PROVIDER, PROJECT_ID, SERVICE_ACCOUNT, ENVIRONMENT
        )
        self.assertEqual(receipt["head_sha"], "b" * 40)
        self.assertEqual(receipt["workflow_sha"], "a" * 40)

    def test_invalid_target_stays_at_r1_and_routes_to_provider_readback(self):
        base = diagnostic.make_base_receipt(
            VALID_PROVIDER, PROJECT_ID, SERVICE_ACCOUNT, ENVIRONMENT
        )
        receipt = diagnostic.apply_sts_result(
            base, 400, {"error": "invalid_target", "error_description": "ignored"}
        )
        self.assertEqual(
            receipt["classification"], "WIF_TARGET_UNAVAILABLE_OR_DISABLED"
        )
        self.assertEqual(receipt["current_level"], "R1")
        self.assertEqual(
            receipt["next_gate"],
            "R2_PROVIDER_EXISTS_ENABLED_AND_AUDIENCE_READBACK",
        )

    def test_successful_sts_exchange_does_not_self_certify_r2(self):
        base = diagnostic.make_base_receipt(
            VALID_PROVIDER, PROJECT_ID, SERVICE_ACCOUNT, ENVIRONMENT
        )
        receipt = diagnostic.apply_sts_result(
            base, 200, {"access_token": "never-render-this-token"}
        )
        self.assertEqual(receipt["classification"], "STS_EXCHANGE_SUCCEEDED")
        self.assertEqual(receipt["current_level"], "R1")
        self.assertEqual(
            receipt["next_gate"], "R2_PROVIDER_AND_SERVICE_ACCOUNT_READBACK"
        )
        self.assertFalse(receipt["service_account_impersonated"])

    def test_service_account_project_mismatch_is_classified(self):
        receipt = diagnostic.run_diagnostic(
            VALID_PROVIDER,
            PROJECT_ID,
            "diagnostic@different-project.iam.gserviceaccount.com",
            {},
        )
        self.assertEqual(
            receipt["classification"], "WIF_SERVICE_ACCOUNT_PROJECT_MISMATCH"
        )
        self.assertFalse(receipt["service_account_project_match"])

    def test_receipt_never_renders_tokens_or_credential_values(self):
        sentinel = "never-render-this-token"
        base = diagnostic.make_base_receipt(
            VALID_PROVIDER, PROJECT_ID, SERVICE_ACCOUNT, ENVIRONMENT
        )
        receipt = diagnostic.apply_sts_result(base, 200, {"access_token": sentinel})
        rendered = diagnostic.render_receipt(receipt)
        decoded = json.loads(rendered)
        self.assertNotIn(sentinel, rendered)
        self.assertFalse(decoded["credential_value_exposed"])
        self.assertFalse(decoded["mutation_performed"])
        self.assertFalse(decoded["model_provider_invoked"])


if __name__ == "__main__":
    unittest.main()
