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
            "READ_APPS_SCRIPT_PROJECT_BOUNDED",
            "1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R",
            "OPERATOR_AUDIENCE",
            "OIDC_ALLOWED_PRINCIPALS",
            "--no-traffic",
            "--tag \"$TAG\"",
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
            "'iam_mutation_performed':False",
            "'traffic_promotion_performed':False",
        ]
        missing = [item for item in required if item not in self.text]
        self.assertFalse(missing, missing)

    def test_forbidden_effect_routes_absent(self) -> None:
        forbidden = [
            "workflow_dispatch:",
            "inputs.confirmation",
            "fo_admin_token",
            "fo-operator-admin-token",
            "gcloud secrets versions access",
            "${{ secrets.",
            "--update-env-vars",
            "run services update-traffic",
            "--to-revisions",
            "--to-tags",
            "--allow-unauthenticated",
            "allusers",
            "add-iam-policy-binding",
            "roles/run.invoker",
            "projects.updatecontent",
        ]
        bad = [item for item in forbidden if item.lower() in self.low]
        self.assertFalse(bad, bad)

    def test_one_strategic_read_request_execution(self) -> None:
        self.assertEqual(1, self.text.count("--data-binary @/tmp/strategic-read/read-request.json"))

    def test_status_precedes_strategic_read(self) -> None:
        self.assertLess(
            self.text.index("/tmp/strategic-read/status-request.json"),
            self.text.index("/tmp/strategic-read/read-request.json"),
        )

    def test_no_traffic_is_proven_before_and_after_read(self) -> None:
        self.assertLess(
            self.text.index("CANDIDATE_TRAFFIC_NOT_ZERO"),
            self.text.index("/tmp/strategic-read/read-request.json"),
        )
        self.assertLess(
            self.text.index("/tmp/strategic-read/read-request.json"),
            self.text.index("CANDIDATE_NOT_ZERO_TRAFFIC_AT_END"),
        )

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
