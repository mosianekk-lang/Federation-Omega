from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "work-plane-storage-authority-census-v1.yml"


class WorkPlaneStorageAuthorityCensusTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_owner_scoped_keyless_read_only_trigger(self):
        self.assertIn("[FO-DISPATCH] WORK_PLANE_STORAGE_AUTHORITY_CENSUS_V1", self.text)
        self.assertIn("github.event.issue.author_association == 'OWNER'", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn("id-token: write", self.text)
        self.assertIn("superior-logic-runtime@sov-hybrid-suite.iam.gserviceaccount.com", self.text)
        self.assertIn("fo-control-plane-sov-hybrid-suite", self.text)

    def test_census_reads_project_and_bucket_policy(self):
        self.assertIn("projects get-iam-policy", self.text)
        self.assertIn("storage buckets get-iam-policy", self.text)
        self.assertIn("storage.objects.get", self.text)
        self.assertIn("storage.objects.create", self.text)
        self.assertIn("storage.objects.delete", self.text)
        self.assertIn("GCS_METADATA_GET_HTTP_403", self.text)

    def test_no_provider_or_iam_mutation_surface(self):
        forbidden = (
            "add-iam-policy-binding",
            "set-iam-policy",
            "gcloud run deploy",
            "gcloud storage cp",
            "gcloud storage rm",
            "gcloud services enable",
            "gcloud secrets versions access",
            "--allow-unauthenticated",
        )
        for marker in forbidden:
            self.assertNotIn(marker, self.text)
        self.assertIn("iam_mutation_performed':False", self.text)
        self.assertIn("provider_data_mutation_performed':False", self.text)
        self.assertIn("raw_policy_emitted':False", self.text)


if __name__ == "__main__":
    unittest.main()
