from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "ops" / "bootstrap_bubbles_gcp_readonly_wif.sh"
PROBE = ROOT / "bubbles" / "provider_surface_probe.py"


class BubblesGcpReadonlyWifContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        cls.probe = PROBE.read_text(encoding="utf-8")

    def test_bootstrap_is_bound_to_provider_backed_project_identity(self):
        self.assertIn('PROJECT_ID="${PROJECT_ID:-sov-hybrid-suite}"', self.bootstrap)
        self.assertIn('EXPECTED_PROJECT_NUMBER="${EXPECTED_PROJECT_NUMBER:-257649435135}"', self.bootstrap)
        self.assertIn("project identity mismatch", self.bootstrap)
        self.assertIn("gcloud projects describe", self.bootstrap)

    def test_bootstrap_uses_keyless_wif_and_never_creates_service_account_keys(self):
        self.assertIn("workload-identity-pools providers create-oidc", self.bootstrap)
        self.assertIn("roles/iam.workloadIdentityUser", self.bootstrap)
        self.assertNotIn("service-accounts keys create", self.bootstrap)
        self.assertNotIn("roles/owner", self.bootstrap)
        self.assertNotIn("roles/editor", self.bootstrap)

    def test_project_roles_are_read_only(self):
        required = {
            "roles/browser",
            "roles/run.viewer",
            "roles/cloudbuild.builds.viewer",
            "roles/iam.serviceAccountViewer",
        }
        for role in required:
            self.assertIn(role, self.bootstrap)
        forbidden = {
            "roles/run.admin",
            "roles/cloudbuild.builds.editor",
            "roles/secretmanager.secretAccessor",
            "roles/resourcemanager.projectIamAdmin",
            "roles/iam.serviceAccountAdmin",
        }
        for role in forbidden:
            self.assertNotIn(role, self.bootstrap)

    def test_oidc_condition_is_repo_id_owner_id_main_and_exact_workflow_bound(self):
        self.assertIn('REPOSITORY_ID="${REPOSITORY_ID:-1292795464}"', self.bootstrap)
        self.assertIn('REPOSITORY_OWNER_ID="${REPOSITORY_OWNER_ID:-261966700}"', self.bootstrap)
        self.assertIn("assertion.repository_id=='${REPOSITORY_ID}'", self.bootstrap)
        self.assertIn("assertion.repository_owner_id=='${REPOSITORY_OWNER_ID}'", self.bootstrap)
        self.assertIn("assertion.ref=='refs/heads/main'", self.bootstrap)
        self.assertIn("assertion.workflow_ref=='${WORKFLOW_REF}'", self.bootstrap)

    def test_probe_is_read_only_and_fails_closed_before_cloud_run_on_project_mismatch(self):
        self.assertIn('RESOURCE_PROJECT_NUMBER = "257649435135"', self.probe)
        self.assertIn('"PROJECT_IDENTITY_MISMATCH"', self.probe)
        self.assertIn('"gcloud", "projects", "describe"', self.probe)
        self.assertIn('"gcloud", "run", "services", "describe"', self.probe)
        self.assertIn('"gcloud", "builds", "list"', self.probe)
        self.assertIn('"mutationAttempted": False', self.probe)
        self.assertNotIn("gcloud run deploy", self.probe)
        self.assertNotIn("gcloud projects add-iam-policy-binding", self.probe)


if __name__ == "__main__":
    unittest.main()
