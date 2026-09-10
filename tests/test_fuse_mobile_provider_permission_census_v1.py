import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fuse-mobile-provider-currentness-v1.yml"
PERMISSION_TEST = "tests/test_fuse_mobile_provider_permission_census_v1.py"


class FuseMobileProviderPermissionCensusV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW.is_file():
            raise unittest.SkipTest("workflow-free export excludes repository workflow controls")
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_reuses_existing_currentness_workflow_and_self_triggers_on_permission_test(self) -> None:
        self.assertIn('name: FUSE Mobile Provider Currentness V1', self.text)
        self.assertIn('".github/workflows/fuse-mobile-provider-currentness-v1.yml"', self.text)
        self.assertIn(f'"{PERMISSION_TEST}"', self.text)
        self.assertIn("workflow_dispatch:", self.text)

    def test_exact_phase_a_permissions_and_provider_native_test_iam_permissions(self) -> None:
        for permission in (
            "serviceusage.services.enable",
            "run.services.update",
            "run.services.setIamPolicy",
        ):
            self.assertIn(permission, self.text)
        self.assertIn(
            "https://cloudresourcemanager.googleapis.com/v1/projects/{project}:testIamPermissions",
            self.text,
        )
        self.assertIn(
            "https://run.googleapis.com/v2/projects/{project}/locations/{region}/services/{service}:testIamPermissions",
            self.text,
        )
        self.assertIn("payload = {'permissions': requested}", self.text)
        self.assertIn("test_permissions(project_url, project_permissions)", self.text)
        self.assertIn("test_permissions(run_url, run_permissions)", self.text)

    def test_permission_census_is_value_free_and_redacted(self) -> None:
        for fragment in (
            "PHASE_A_PERMISSION_RECEIPT.json",
            "FUSE_MOBILE_PHASE_A_PERMISSION_CENSUS_V1",
            "'tested_permissions'",
            "'granted_permissions'",
            "'missing_permissions'",
            "'http_status'",
            "'response_sha256'",
            "'credential_value_recorded': False",
            "'raw_response_body_recorded': False",
            "'provider_mutation_performed': False",
            "'iam_mutation_performed': False",
            "'api_mutation_performed': False",
            "'traffic_change_performed': False",
            "'secret_access_performed': False",
            "'model_inference_performed': False",
        ):
            self.assertIn(fragment, self.text)
        self.assertNotIn("print(access_token", self.text)
        self.assertNotIn("print(token", self.text)

    def test_access_token_is_ephemeral_and_masked(self) -> None:
        self.assertIn('ACCESS_TOKEN="$(gcloud auth print-access-token)"', self.text)
        self.assertIn('echo "::add-mask::$ACCESS_TOKEN"', self.text)
        self.assertIn("export ACCESS_TOKEN", self.text)
        self.assertIn("unset ACCESS_TOKEN", self.text)
        self.assertIn("Bearer {token}", self.text)

    def test_no_provider_mutation_commands_are_added_to_currentness_workflow(self) -> None:
        forbidden = (
            "gcloud services enable",
            "gcloud services disable",
            "gcloud run services update ",
            "gcloud run deploy",
            "add-iam-policy-binding",
            "set-iam-policy",
            "update-traffic",
            "--allow-unauthenticated",
            "gcloud secrets versions access",
            "gcloud secrets versions add",
            "generateContent",
            "GEMINI_API_KEY",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, self.text)

    def test_phase_a_state_fails_closed_when_any_permission_is_missing_or_unreadable(self) -> None:
        self.assertIn("'READY' if not missing and all(status == 200", self.text)
        self.assertIn("else 'PERMISSION_HELD'", self.text)
        self.assertIn("'phase_a_state': phase_a_state", self.text)

    def test_permission_receipt_is_uploaded_with_existing_currentness_receipt(self) -> None:
        self.assertRegex(
            self.text,
            re.compile(
                r"path:\s*\|\s*\n"
                r"\s*/tmp/fuse-mobile-provider-currentness/PROVIDER_CURRENTNESS_RECEIPT\.json\s*\n"
                r"\s*/tmp/fuse-mobile-provider-currentness/PHASE_A_PERMISSION_RECEIPT\.json",
                re.MULTILINE,
            ),
        )


if __name__ == "__main__":
    unittest.main()
